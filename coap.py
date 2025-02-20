import asyncio
from aiocoap import *
from Crypto.Cipher import AES

COAP_SERVER_IPV6 = "[2001:470:7347:c618:64b5:69f7:b5d:1f81]"
COAP_RESOURCE_PATH = "sensorData"
AES_KEY = b'TRusVHwckwYzB7np'


async def call_coap_server():
    protocol = await Context.create_client_context()
    uri = f"coap://{COAP_SERVER_IPV6}/{COAP_RESOURCE_PATH}"

    request = Message(code=1, uri=uri)

    try:
        response = await protocol.request(request).response
        # coap_value = response.payload.decode('utf-8')
        coap_value = decrypt_coap_value(response.payload)
        return coap_value
    except Exception as e:
        return -1

async def call_coap_server_with_timeout():
    try:
        return await asyncio.wait_for(call_coap_server(), timeout=4.0)
    except asyncio.TimeoutError:
        return "Failed to call CoAP server: Timeout"

def decrypt_coap_value(encrypted_value):
    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    decrypted_bytes = cipher.decrypt(encrypted_value)
    return decrypted_bytes.decode('utf-8')