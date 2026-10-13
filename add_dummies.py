import sqlite3
from datetime import date

conn = sqlite3.connect('runs.db')
c = conn.cursor()

# Get the schema of users to see if we need a pin
c.execute("PRAGMA table_info(users)")
print(c.fetchall())

try:
    c.execute("INSERT INTO users (username, display_name, status, pin) VALUES ('david_goggins', 'David Goggins', 'active', '0000')")
    goggins_id = c.lastrowid
    c.execute("INSERT INTO users (username, display_name, status, pin) VALUES ('eliud_k', 'Eliud Kipchoge', 'active', '0000')")
    eliud_id = c.lastrowid
    
    today = date.today().isoformat()
    c.execute("INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, 10.0, 45, 4.5, 600)", (goggins_id, today))
    c.execute("INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, 42.2, 120, 2.8, 2500)", (eliud_id, today))
    conn.commit()
    print("Added dummies!")
except Exception as e:
    print("Error:", e)
conn.close()
