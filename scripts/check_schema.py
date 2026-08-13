import os
import sqlite3

# Resolve project root (one level up from scripts/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "runs.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.execute('PRAGMA table_info(runs)')
print('Columns in runs table:')
for row in cursor:
    print(f"  {row[1]} ({row[2]})")
conn.close()
#Helllo