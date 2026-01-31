import sqlite3

conn = sqlite3.connect('runs.db')
cursor = conn.execute('PRAGMA table_info(runs)')
print('Columns in runs table:')
for row in cursor:
    print(f"  {row[1]} ({row[2]})")
conn.close()
