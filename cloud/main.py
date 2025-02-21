import difflib
from datetime import datetime

import requests
from quart import Quart, request
import json
from database import init_db, get_latest_entries, store_coap_data_sensor, count_entries_per_day
from coap import call_coap_server_with_timeout

app = Quart(__name__)

TELEGRAM_BOT_TOKEN = '7575257718:AAHQqlADksOXihUAMN2rc6-SjUAdcygOa2Q'
EC2_PUBLIC_HTTPS_URL = 'https://iotaws-project.ddns.net'
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

init_db()

def is_similar_command(input_text, reference, cutoff=0.7):
    input_text = input_text.lower().strip()
    match = difflib.get_close_matches(input_text, [reference], n=1, cutoff=cutoff)
    return bool(match)

@app.route('/test', methods=['GET'])
async def test():
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
    url = request.args.get('url', EC2_PUBLIC_HTTPS_URL)
    webhook_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={url}/webhook"
    response = requests.get(webhook_url)
    print("Webhook setup response:", response.json())
    return response.json()


@app.route('/webhook', methods=['POST'])
async def webhook():
    data = await request.get_json()
    message = data.get('message', {})
    chat_id = message.get('chat', {}).get('id')
    text = message.get('text', '')

    parse_mode = None  # Use this later if we need special formatting (HTML)

    if is_similar_command(text, "read sensor") or text == "1":
        # This command replaces "call coap"
        requests.post(
            f"{TELEGRAM_URL}/sendChatAction",
            data={"chat_id": chat_id, "action": "typing"}
        )
        coap_response = await call_coap_server_with_timeout()
        if coap_response and coap_response != "Failed to call CoAP server: Timeout":
            try:
                sensor_data = json.loads(coap_response.rstrip("\x00"))
                store_coap_data_sensor(sensor_data['d'][1], sensor_data['d'][0])
                temp = sensor_data['d'][0]
                hum = sensor_data['d'][1] / 10
                print(f"Temperature: {temp}°C, Humidity: {hum}%")
                response_text = (
                    f"Sensor Updated:\n"
                    f"Temperature: {temp}.0°C\n"
                    f"Humidity: {hum}%"
                )
            except json.JSONDecodeError:
                response_text = "Failed to decode sensor response."
        else:
            response_text = "Failed to get a response from the sensor server."

    elif is_similar_command(text, "show history") or text == "2":
        # This command replaces "hist"
        entries = get_latest_entries()
        # Use only the last 10 entries if there are more than 10
        if len(entries) > 10:
            entries = entries[-10:]

        # Convert stored values (e.g., 240 -> 24.0) for temperature and humidity,
        # and update each entry with the converted values.
        converted_entries = []
        for entry in entries:
            try:
                temp_converted = float(entry['value_temp'])
            except (ValueError, TypeError):
                temp_converted = 0.0
            try:
                hum_converted = float(entry['value_hum']) / 10
            except (ValueError, TypeError):
                hum_converted = 0.0
            entry['temp_converted'] = temp_converted
            entry['hum_converted'] = hum_converted
            converted_entries.append(entry)

        # Calculate averages using the converted values.
        avg_temp = sum(e['temp_converted'] for e in converted_entries) / len(converted_entries)
        avg_hum = sum(e['hum_converted'] for e in converted_entries) / len(converted_entries)

        # Build a table using Unicode box-drawing characters.
        # Adjusted column widths for a cleaner display.
        table = "┌─────────────┬──────────┬──────────┐\n"
        table += "│ Timestamp   │ Temp(°C) │ Humidity │\n"
        table += "├─────────────┼──────────┼──────────┤\n"
        for entry in converted_entries:
            raw_timestamp = entry.get('timestamp', '')
            # Format the timestamp from "YYYY-MM-DD HH:MM:SS" to "DDMon HH:MM" (e.g., "02Feb 13:53")
            try:
                dt = datetime.strptime(raw_timestamp, "%Y-%m-%d %H:%M:%S")
                formatted_timestamp = dt.strftime("%d%b %H:%M")
            except ValueError:
                formatted_timestamp = raw_timestamp
            temp_value = entry['temp_converted']
            hum_value = entry['hum_converted']
            # The following line creates a row for the table:
            table += f"│ {formatted_timestamp:<11} │ {temp_value:>6.1f}°C │ {hum_value:>7.1f}% │\n"
        table += "├─────────────┼──────────┼──────────┤\n"
        table += f"│ Average     │ {avg_temp:>6.1f}°C │ {avg_hum:>7.1f}% │\n"
        table += "└─────────────┴──────────┴──────────┘"

        response_text = f"<pre>{table}</pre>"
        parse_mode = "HTML"

    elif is_similar_command(text, "daily amount") or text == "3":
        # Fetch entry counts per day
        daily_counts = count_entries_per_day()

        if not daily_counts:
            response_text = "No sensor data recorded yet."
        else:
            # Format the response text as a table
            table = "┌────────────┬───────────┐\n"
            table += "│ Date       │ Entries   │\n"
            table += "├────────────┼───────────┤\n"
            for entry in daily_counts:
                table += f"│ {entry['date']} │ {entry['entry_count']:>6}    │\n"
            table += "└────────────┴───────────┘"

            response_text = f"<pre>{table}</pre>"
            parse_mode = "HTML"

    else:
        # For any unknown command, send a help message listing the valid commands.
        commands_list = (
            "Supported commands:\n"
            "1. read sensor - Fetches the latest sensor data\n"
            "2. show history  - Displays the last 10 sensor readings with averages\n"
            "3. daily amount - Shows the number of sensor readings per day"
        )
        response_text = f"'{text}' is not a valid command.\n{commands_list}"

    payload = {"chat_id": chat_id, "text": response_text}
    if parse_mode:
        payload["parse_mode"] = parse_mode

    requests.post(f"{TELEGRAM_URL}/sendMessage", data=payload)
    return {"status": "ok"}, 200

@app.route('/webhook_old', methods=['POST'])
async def webhook_old():
    data = await request.get_json()
    message = data.get('message', {})
    chat_id = message.get('chat', {}).get('id')
    text = message.get('text', '')

    response_text = "Hello! You sent: " + text

    if text.lower() == "call coap":
        requests.post(f"{TELEGRAM_URL}/sendChatAction", data={"chat_id": chat_id, "action": "typing"})
        coap_response = await call_coap_server_with_timeout()
        if coap_response and coap_response != "Failed to call CoAP server: Timeout":
            try:
                data = json.loads(coap_response)
                store_coap_data_sensor(data['humidity'], data['temperature'])
                response_text = f"CoAP Server Response: {coap_response}"
            except json.JSONDecodeError:
                response_text = "Failed to decode CoAP server response."
        else:
            response_text = "Failed to get a response from the CoAP server."
    elif text.lower() == "hist":
        entries = get_latest_entries()
        response_text = "Latest 20 entries:\n"
        for entry in entries:
            response_text += f"{entry['timestamp']}: Temp={entry['value_temp']}, Hum={entry['value_hum']}\n"

    requests.post(
        f"{TELEGRAM_URL}/sendMessage",
        data={"chat_id": chat_id, "text": response_text}
    )

    return {"status": "ok"}, 200
