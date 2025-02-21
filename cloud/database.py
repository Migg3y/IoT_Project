from datetime import datetime
import sqlite3

def init_db():
    conn = sqlite3.connect('coap_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS coap_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            value_temp TEXT NOT NULL,
            value_hum TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def store_coap_data_sensor(hum, temp):
    conn = sqlite3.connect('coap_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO coap_data (timestamp, value_hum, value_temp)
        VALUES (?, ?, ?)
    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), hum, temp))
    conn.commit()
    conn.close()

def get_latest_entries():
    conn = sqlite3.connect('coap_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT timestamp, value_temp, value_hum
        FROM coap_data
        ORDER BY timestamp DESC
        LIMIT 10
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [{"timestamp": row[0], "value_temp": row[1], "value_hum": row[2]} for row in rows]

def count_entries_per_day():
    conn = sqlite3.connect('coap_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DATE(timestamp) AS date, COUNT(*) AS entry_count
        FROM coap_data
        GROUP BY DATE(timestamp)
        ORDER BY date DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [{"date": row[0], "entry_count": row[1]} for row in rows]
