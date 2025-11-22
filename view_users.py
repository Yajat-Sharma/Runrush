import sqlite3

conn = sqlite3.connect("runs.db")
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT id, username, pin, display_name, weight FROM users").fetchall()
conn.close()

for r in rows:
    print(
        f"id={r['id']}, username={r['username']}, "
        f"pin={r['pin']}, name={r['display_name']}, weight={r['weight']}"
    )

#python view_users.py TO RUN THIS CODE