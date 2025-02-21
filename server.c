/*
 * Copyright (c) 2015-2017 Ken Bannister. All rights reserved.
 *
 * This file is subject to the terms and conditions of the GNU Lesser
 * General Public License v2.1. See the file LICENSE in the top level
 * directory for more details.
 */

/**
 * @ingroup     examples
 * @{
 *
 * @file
 * @brief       gcoap CLI support
 *
 * @author      Ken Bannister <kb2ma@runbox.com>
 * @author      Hauke Petersen <hauke.petersen@fu-berlin.de>
 *
 * @}
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "dht.h"
#include "dht_params.h"
#include "xtimer.h"
#include "shell.h"
#include "saul.h"
#include "saul_reg.h"
#include "tinycrypt/aes.h"
#include "tinycrypt/constants.h"
#include "tinycrypt/utils.h"
#include "tinycrypt/cbc_mode.h"
#include "base64.h"

#include "crypto/ciphers.h"

#include "event/periodic_callback.h"
#include "event/thread.h"
#include "fmt.h"
#include "net/gcoap.h"
#include "net/utils.h"
#include "od.h"
#include "periph/rtc.h"
#include "time_units.h"

#include "gcoap_example.h"

#define ENABLE_DEBUG 0
#include "debug.h"

#define AES_BLOCK_SIZE 16  // AES block size in bytes (128 bits)
#define AES_KEY_SIZE 16  // AES block size in bytes (128 bits)

static dht_t dev;
int16_t temp;
int16_t hum; 

// AES key (128-bit, 16 bytes)
static const uint8_t aes_key[AES_KEY_SIZE] = {
    0x54,0x52,0x75,0x73,0x56,0x48,0x77,0x63,
    0x6B,0x77,0x59,0x7A,0x42,0x37,0x6E,0x70
};

void encrypt_message(const uint8_t *input, size_t len, uint8_t *output) {
    uint8_t plain_text[AES_BLOCK_SIZE] = {0};  // Buffer for input data (AES block size)
    uint8_t cipher_text[AES_BLOCK_SIZE];       // Buffer for encrypted data
    cipher_t cipher;

    // Ensure the input data fits in one AES block (16 bytes)
    if (len > AES_BLOCK_SIZE) {
        printf("Input too large for AES block size\n");
        return;
    }
    memcpy(plain_text, input, len);

    // Initialize AES cipher with the key
    if (cipher_init(&cipher, CIPHER_AES, aes_key, AES_KEY_SIZE) < 0) {
        printf("Cipher init failed!\n");
        return;
    }

    // Encrypt the input data
    if (cipher_encrypt(&cipher, plain_text, cipher_text) < 0) {
        printf("Cipher encryption failed!\n");
        return;
    }

    // Copy the encrypted data to the output buffer
    memcpy(output, cipher_text, AES_BLOCK_SIZE);
}

static const dht_params_t my_params = {
        .type = DHT11,
        .pin = GPIO_PIN(0, 31) // Adjust this pin as per your wiring
};

static ssize_t _encode_link(const coap_resource_t *resource, char *buf,
                            size_t maxlen, coap_link_encoder_ctx_t *context);
/* static ssize_t _humidity_handler(coap_pkt_t* pdu, uint8_t *buf, size_t len, coap_request_ctx_t *ctx); */
static ssize_t _sensorData_handler(coap_pkt_t* pdu, uint8_t *buf, size_t len, coap_request_ctx_t *ctx);

/* CoAP resources. Must be sorted by path (ASCII order). */
static const coap_resource_t _resources[] = {
	{"/sensorData", COAP_GET, _sensorData_handler, NULL},
};

static const char *_link_params[] = {
    ";ct=0;rt=\"count\";obs",
    NULL
};

static gcoap_listener_t _listener = {
    &_resources[0],
    ARRAY_SIZE(_resources),
    GCOAP_SOCKET_TYPE_UNDEF,
    _encode_link,
    NULL,
    NULL
};


/* Adds link format params to resource list */
static ssize_t _encode_link(const coap_resource_t *resource, char *buf,
                            size_t maxlen, coap_link_encoder_ctx_t *context) {
    ssize_t res = gcoap_encode_link(resource, buf, maxlen, context);
    if (res > 0) {
        if (_link_params[context->link_pos]
                && (strlen(_link_params[context->link_pos]) < (maxlen - res))) {
            if (buf) {
                memcpy(buf+res, _link_params[context->link_pos],
                       strlen(_link_params[context->link_pos]));
            }
            return res + strlen(_link_params[context->link_pos]);
        }
    }

    return res;
}

void read_sensorData(void) {
    dht_read(&dev, &temp, &hum);
    printf("\nDHT values - temp: %d.%d°C - relative humidity: %d.%d%%\n", temp / 10, temp % 10, hum / 10, hum % 10);
}

static ssize_t _sensorData_handler(coap_pkt_t *pdu, uint8_t *buf, size_t len, coap_request_ctx_t *ctx) {
    (void)ctx;
    read_sensorData();
    
    // Initialize CoAP response
    gcoap_resp_init(pdu, buf, len, COAP_CODE_CONTENT);

    // Optionally, specify the content type (application/json or plain text for example)
    coap_opt_add_format(pdu, COAP_FORMAT_AIF_JSON);

    // Prepare the JSON payload
    size_t len_written = snprintf((char *)pdu->payload, 1024, 
                                  "{\"d\":[%d,%d]}", temp/10, hum);

    // Print the original (plaintext) payload
    printf("Original Payload: %s\n", pdu->payload);

    // Encrypt the payload
    uint8_t encrypted_payload[AES_BLOCK_SIZE];  // Adjust the buffer size as needed
    encrypt_message(pdu->payload, len_written, encrypted_payload);

    // Print the encrypted payload (in hexadecimal)
    printf("Encrypted Payload: ");
    for (size_t i = 0; i < AES_KEY_SIZE; i++) {
        printf("%02x ", encrypted_payload[i]);
    }
    printf("\n %hhn", encrypted_payload);

    // Send the encrypted payload
    size_t resp_len = coap_opt_finish(pdu, COAP_OPT_FINISH_PAYLOAD);
    memcpy(pdu->payload, encrypted_payload, AES_BLOCK_SIZE);

    resp_len += AES_BLOCK_SIZE;

    return resp_len;
}

/* static ssize_t _sensorData_handler(coap_pkt_t *pdu, uint8_t *buf, size_t len, coap_request_ctx_t *ctx)
{   
    (void)ctx;
    read_sensorData();
    
    // Initialize CoAP response
    gcoap_resp_init(pdu, buf, len, COAP_CODE_CONTENT);

    // Optionally, specify the content type (application/json or plain text for example)
    coap_opt_add_format(pdu, COAP_FORMAT_AIF_JSON);

    // Format the response payload (temperature in Celsius)
    size_t resp_len = coap_opt_finish(pdu, COAP_OPT_FINISH_PAYLOAD);
    size_t len_written = snprintf((char *)pdu->payload, 1024, 
                                  "{\"temperature\": %d, \"humidity\": %d}", temp, hum);
    
    resp_len += len_written;

    return resp_len;
} */

/* static ssize_t _temperature_handler(coap_pkt_t *pdu, uint8_t *buf, size_t len, coap_request_ctx_t *ctx)
{
    (void)ctx;
    int32_t temp_celsius = read_sensorData();  // Call the temperature read function

    // Initialize CoAP response
    gcoap_resp_init(pdu, buf, len, COAP_CODE_CONTENT);

    // Optionally, specify the content type (application/json or plain text for example)
    coap_opt_add_format(pdu, COAP_FORMAT_TEXT);

    // Format the response payload (temperature in Celsius)
    size_t resp_len = coap_opt_finish(pdu, COAP_OPT_FINISH_PAYLOAD);
    resp_len += fmt_u32_dec((char *)pdu->payload, temp_celsius);

    return resp_len;
} */


void notify_observers(void)
{
}

void server_init(void)
{
    int res = dht_init(&dev, &my_params);
    if (res != DHT_OK) {
        printf("Failed to initialize DHT sensor. Error code: %d\n", res);
    } else {
        printf("DHT sensor connected\n");
        xtimer_usleep(1000000);
   	}

    gcoap_register_listener(&_listener);
}
