import difflib
from datetime import datetime

import requests
from quart import Quart, request
import json
from database import init_db, get_latest_entries, store_coap_data_sensor, count_entries_per_day
from coap import call_coap_server_with_timeout

app = Quart(__name__)

# Telegram Bot API Token and EC2 Public HTTPS URL - Consider moving these to environment variables for security.
TELEGRAM_BOT_TOKEN = '7575257718:AAHQqlADksOXihUAMN2rc6-SjUAdcygOa2Q'
EC2_PUBLIC_HTTPS_URL = 'https://iotaws-project.ddns.net'
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

init_db() # Initialize the database when the application starts.

def is_similar_command(input_text, reference, cutoff=0.7):
    """
    Checks if the input text is similar to a reference command.

    Uses difflib to find close matches, useful for handling slight variations in user commands.
    Args:
        input_text (str): The text to check for similarity.
        reference (str): The reference command to compare against.
        cutoff (float, optional): The similarity cutoff value (0.0 to 1.0). Defaults to 0.7.
    Returns:
        bool: True if the input text is similar to the reference, False otherwise.
    """
    input_text = input_text.lower().strip()
    match = difflib.get_close_matches(input_text, [reference], n=1, cutoff=cutoff)
    return bool(match)

@app.route('/test', methods=['GET'])
async def test():
    """
    Simple health check endpoint.

    Returns a basic HTML page indicating the service is running.
    Useful for monitoring and verifying the application is active.
    """
    return '''
    <html>
        <head><title>Service Status</title></head>
        <body>
            <h1>Service is running...</h1>
        </body>
    </html>
    '''

@app.route('/update_webhook', methods=['GET'])
def update_webhook():
    """
    Endpoint to update the Telegram bot webhook.

    Sets the webhook URL for the Telegram bot to receive updates.
    The URL is configurable via the 'url' query parameter, defaulting to EC2_PUBLIC_HTTPS_URL.
    """
    url = request.args.get('url', EC2_PUBLIC_HTTPS_URL)
    webhook_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={url}/webhook"
    response = requests.get(webhook_url)
    print("Webhook setup response:", response.json()) # Logs the webhook setup response for debugging.
    return response.json()


@app.route('/webhook', methods=['POST'])
async def webhook():
    """
    Webhook endpoint for handling Telegram bot updates.

    Receives updates from Telegram, parses commands, interacts with CoAP server and database,
    and sends responses back to the Telegram chat.
    """
    data = await request.get_json() # Get updates from Telegram as JSON
    message = data.get('message', {}) # Extract message object
    chat_id = message.get('chat', {}).get('id') # Extract chat ID to respond to
    text = message.get('text', '') # Extract message text content

    parse_mode = None  # Initialize parse mode for Telegram message formatting (e.g., HTML)

    if is_similar_command(text, "read sensor") or text == "1":
        # Handle "read sensor" command (or "1") to fetch and display sensor data.
        requests.post(
            f"{TELEGRAM_URL}/sendChatAction",
            data={"chat_id": chat_id, "action": "typing"} # Send 'typing' action to Telegram to indicate processing.
        )
        coap_response = await call_coap_server_with_timeout() # Call CoAP server to get sensor data

        if coap_response and coap_response != "Failed to call CoAP server: Timeout":
            try:
                sensor_data = json.loads(coap_response.rstrip("\x00")) # Load JSON sensor data, remove trailing null bytes
                store_coap_data_sensor(sensor_data['d'][1], sensor_data['d'][0]) # Store received sensor data in the database
                temp = sensor_data['d'][0]
                hum = sensor_data['d'][1] / 10
                print(f"Temperature: {temp}°C, Humidity: {hum}%") # Log sensor data to console
                response_text = (
                    f"Sensor Updated:\n"
                    f"Temperature: {temp}.0°C\n"
                    f"Humidity: {hum}%"
                )
            except json.JSONDecodeError:
                response_text = "Failed to decode sensor response." # Handle JSON decode errors from CoAP response
        else:
            response_text = "Failed to get a response from the sensor server." # Handle timeout or CoAP call failure

    elif is_similar_command(text, "show history") or text == "2":
        # Handle "show history" command (or "2") to display historical sensor data.
        entries = get_latest_entries() # Fetch latest sensor entries from the database
        if not entries:
            response_text = "The database is empty. Use the 'read sensor' command to first fill in data." # Inform user if no data in database
        else:
            if len(entries) > 10:
                entries = entries[-10:] # Limit to last 10 entries for display

            converted_entries = []
            for entry in entries:
                # Convert and store temperature and humidity values for easier calculation and display
                try:
                    temp_converted = float(entry['value_temp'])
                except (ValueError, TypeError):
                    temp_converted = 0.0 # Default to 0.0 in case of conversion error
                try:
                    hum_converted = float(entry['value_hum']) / 10
                except (ValueError, TypeError):
                    hum_converted = 0.0 # Default to 0.0 in case of conversion error
                entry['temp_converted'] = temp_converted
                entry['hum_converted'] = hum_converted
                converted_entries.append(entry)

            avg_temp = sum(e['temp_converted'] for e in converted_entries) / len(converted_entries) # Calculate average temperature
            avg_hum = sum(e['hum_converted'] for e in converted_entries) / len(converted_entries) # Calculate average humidity

            # Create a formatted table using Unicode characters for historical data display.
            table = "┌─────────────┬──────────┬──────────┐\n"
            table += "│ Timestamp   │ Temp(°C) │ Humidity │\n"
            table += "├─────────────┼──────────┼──────────┤\n"
            for entry in converted_entries:
                raw_timestamp = entry.get('timestamp', '')
                try:
                    dt = datetime.strptime(raw_timestamp, "%Y-%m-%d %H:%M:%S") # Parse timestamp string to datetime object
                    formatted_timestamp = dt.strftime("%d%b %H:%M") # Format timestamp for display (e.g., "02Feb 13:53")
                except ValueError:
                    formatted_timestamp = raw_timestamp # Use raw timestamp in case of parsing error
                temp_value = entry['temp_converted']
                hum_value = entry['hum_converted']
                table += f"│ {formatted_timestamp:<11} │ {temp_value:>6.1f}°C │ {hum_value:>7.1f}% │\n"
            table += "├─────────────┼──────────┼──────────┤\n"
            table += f"│ Average     │ {avg_temp:>6.1f}°C │ {avg_hum:>7.1f}% │\n"
            table += "└─────────────┴──────────┴──────────┘"

            response_text = f"<pre>{table}</pre>" # Use <pre> tag for monospace formatting in HTML
            parse_mode = "HTML" # Set parse mode to HTML for formatted table

    elif is_similar_command(text, "daily amount") or text == "3":
        # Handle "daily amount" command (or "3") to show daily entry counts.
        daily_counts = count_entries_per_day() # Fetch daily entry counts from the database

        if not daily_counts:
            response_text = "The database is empty. Use the 'read sensor' command to first fill in data." # Inform user if no data
        else:
            # Format the daily counts as a table.
            table = "┌────────────┬───────────┐\n"
            table += "│ Date       │ Entries   │\n"
            table += "├────────────┼───────────┤\n"
            for entry in daily_counts:
                table += f"│ {entry['date']} │ {entry['entry_count']:>6}    │\n"
            table += "└────────────┴───────────┘"

            response_text = f"<pre>{table}</pre>" # Use <pre> for monospace table
            parse_mode = "HTML" # Set parse mode to HTML

    else:
        # Handle unknown commands by providing a help message.
        commands_list = (
            "Supported commands:\n"
            "1. read sensor - Fetches the latest sensor data\n"
            "2. show history  - Displays the last 10 sensor readings with averages\n"
            "3. daily amount - Shows the number of sensor readings per day"
        )
        response_text = f"'{text}' is not a valid command.\n{commands_list}" # Construct help message

    payload = {"chat_id": chat_id, "text": response_text} # Construct payload for Telegram sendMessage API
    if parse_mode:
        payload["parse_mode"] = parse_mode # Add parse mode to payload if needed for formatting

    requests.post(f"{TELEGRAM_URL}/sendMessage", data=payload) # Send message back to Telegram
    return {"status": "ok"}, 200 # Return success status
