from datetime import datetime
import sqlite3

def init_db():
    """
    Initializes the SQLite database.

    Creates the 'coap_data' table if it does not already exist.
    The table stores sensor data with timestamp, temperature, and humidity values.
    """
    conn = sqlite3.connect('coap_data.db') # Connect to SQLite database (creates if not exists)
    cursor = conn.cursor() # Create a cursor object to execute SQL commands
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS coap_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            value_temp TEXT NOT NULL,
            value_hum TEXT NOT NULL
        )
    ''') # SQL command to create table if not exists, with columns for id, timestamp, temperature, and humidity
    conn.commit() # Commit the changes to the database to persist table creation
    conn.close() # Close the database connection


def store_coap_data_sensor(hum, temp):
    """
    Stores sensor data (humidity and temperature) into the database.

    Inserts a new record into the 'coap_data' table with the current timestamp and sensor values.
    Args:
        hum (str): Humidity value as a string.
        temp (str): Temperature value as a string.
    """
    conn = sqlite3.connect('coap_data.db') # Connect to the database
    cursor = conn.cursor() # Create a cursor
    cursor.execute('''
        INSERT INTO coap_data (timestamp, value_hum, value_temp)
        VALUES (?, ?, ?)
    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), hum, temp)) # SQL command to insert data with current timestamp
    conn.commit() # Save the inserted data
    conn.close() # Close the connection

def get_latest_entries():
    """
    Retrieves the latest sensor entries from the database.

    Fetches the most recent 10 entries from the 'coap_data' table, ordered by timestamp in descending order.
    Returns:
        list: A list of dictionaries, each representing a database entry with timestamp, value_temp, and value_hum.
              Returns an empty list if there are no entries or in case of an error.
    """
    conn = sqlite3.connect('coap_data.db') # Connect to the database
    cursor = conn.cursor() # Create a cursor
    cursor.execute('''
        SELECT timestamp, value_temp, value_hum
        FROM coap_data
        ORDER BY timestamp DESC
        LIMIT 10
    ''') # SQL command to select timestamp, temp, hum from the latest 10 entries
    rows = cursor.fetchall() # Fetch all selected rows
    conn.close() # Close the connection
    return [{"timestamp": row[0], "value_temp": row[1], "value_hum": row[2]} for row in rows] # Format rows as list of dictionaries

def count_entries_per_day():
    """
    Counts the number of sensor entries for each day.

    Queries the database to count entries grouped by date, ordered by date in descending order.
    Returns:
        list: A list of dictionaries, each containing 'date' and 'entry_count'.
              Returns an empty list if there are no entries or in case of an error.
    """
    conn = sqlite3.connect('coap_data.db') # Connect to the database
    cursor = conn.cursor() # Create a cursor
    cursor.execute('''
        SELECT DATE(timestamp) AS date, COUNT(*) AS entry_count
        FROM coap_data
        GROUP BY DATE(timestamp)
        ORDER BY date DESC
    ''') # SQL query to count entries per day, grouped by date and ordered descending
    rows = cursor.fetchall() # Fetch all rows
    conn.close() # Close the connection
    return [{"date": row[0], "entry_count": row[1]} for row in rows] # Format rows as list of dictionaries
