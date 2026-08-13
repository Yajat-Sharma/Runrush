import os
import sqlite3

# Resolve project root (one level up from scripts/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "runs.db")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT id, username, pin, display_name, weight FROM users").fetchall()
conn.close()

for r in rows:
    print(
        f"id={r['id']}, username={r['username']}, "
        f"pin={r['pin']}, name={r['display_name']}, weight={r['weight']}"
    )

#python view_users.py TO RUN THIS CODE