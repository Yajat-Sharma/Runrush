import sqlite3
conn = sqlite3.connect('runs.db')
cur = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='runs';")
print(cur.fetchone()[0])
conn.close()
