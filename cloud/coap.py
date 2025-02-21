import asyncio
from aiocoap import *
from Crypto.Cipher import AES

# CoAP Server IPv6 Address and Resource Path
COAP_SERVER_IPV6 = "[2001:470:7347:c618:64b5:69f7:b5d:1f81]" # Set this to the IPv6 address of the CoAP server
COAP_RESOURCE_PATH = "sensorData"
AES_KEY = b'TRusVHwckwYzB7np' # AES encryption key (16 bytes)

async def call_coap_server():
    """
    Asynchronously calls the CoAP server to fetch sensor data.

    Establishes a CoAP client context, sends a request to the specified URI,
    decrypts the response payload, and returns the decrypted sensor value.

    """
    protocol = await Context.create_client_context() # Create CoAP client context
    uri = f"coap://{COAP_SERVER_IPV6}/{COAP_RESOURCE_PATH}" # Construct CoAP URI

    request = Message(code=1, uri=uri) # Create CoAP request message (GET request - code 1)

    try:
        response = await protocol.request(request).response # Send request and wait for response
        coap_value = decrypt_coap_value(response.payload) # Decrypt the payload of the CoAP response
        return coap_value
    except Exception as e:
        print(f"Error calling CoAP server: {e}") # Log any exceptions during CoAP call for debugging.
        return -1 # Return -1 to indicate an error

async def call_coap_server_with_timeout():
    """
    Calls the CoAP server with a timeout.

    Wraps the call_coap_server function with a timeout to prevent indefinite waiting.
    """
    try:
        return await asyncio.wait_for(call_coap_server(), timeout=4.0) # Wait for CoAP call with a 4-second timeout
    except asyncio.TimeoutError:
        return "Failed to call CoAP server: Timeout" # Return timeout message if CoAP call exceeds timeout

def decrypt_coap_value(encrypted_value):
    """
    Decrypts the encrypted CoAP value using AES decryption.

    Utilizes AES in ECB mode with a predefined key to decrypt the sensor data.
    Args:
        encrypted_value (bytes): The encrypted payload from the CoAP response.
    """
    cipher = AES.new(AES_KEY, AES.MODE_ECB) # Initialize AES cipher in ECB mode with the AES key
    decrypted_bytes = cipher.decrypt(encrypted_value) # Decrypt the encrypted value
    return decrypted_bytes.decode('utf-8') # Decode the decrypted bytes to a UTF-8 string
