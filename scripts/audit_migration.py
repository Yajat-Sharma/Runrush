import os
import sqlite3
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

SQLITE_PATH = "runs.db"
PG_URL = os.environ.get("DATABASE_URL")

# --- SQLite side ---
sqlite_conn = sqlite3.connect(SQLITE_PATH)
sqlite_conn.row_factory = sqlite3.Row
sqlite_rows = sqlite_conn.execute("SELECT id, username, google_id, google_email FROM users ORDER BY id").fetchall()

print("=" * 80)
print("SQLite (Source of Truth)")
print("=" * 80)
print(f"{'ID':<6} {'Username':<20} {'Google ID':<25} {'Google Email'}")
print("-" * 80)
for r in sqlite_rows:
    print(f"{r['id']:<6} {r['username']:<20} {str(r['google_id'] or 'NULL'):<25} {r['google_email'] or 'NULL'}")

sqlite_conn.close()

# --- PostgreSQL (Neon) side ---
pg_conn = psycopg2.connect(PG_URL)
pg_cur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
pg_cur.execute("SELECT id, username, google_id, google_email FROM users ORDER BY id")
pg_rows = pg_cur.fetchall()

print()
print("=" * 80)
print("Neon PostgreSQL (Current State After Fix)")
print("=" * 80)
print(f"{'ID':<6} {'Username':<20} {'Google ID':<25} {'Google Email'}")
print("-" * 80)
for r in pg_rows:
    print(f"{r['id']:<6} {r['username']:<20} {str(r['google_id'] or 'NULL'):<25} {r['google_email'] or 'NULL'}")

# --- Cross-check: does every SQLite id+username pair match Neon id+username? ---
print()
print("=" * 80)
print("CROSS-CHECK: ID-to-Username Consistency")
print("=" * 80)

pg_map = {r['id']: r['username'] for r in pg_rows}
all_match = True
for r in sqlite_rows:
    sid = r['id']
    s_user = r['username']
    pg_user = pg_map.get(sid, "MISSING")
    match = "OK" if s_user == pg_user else "MISMATCH"
    if match != "OK":
        all_match = False
    print(f"  SQLite ID {sid} username={s_user:<20}  Neon ID {sid} username={pg_user:<20}  => {match}")

if all_match:
    print("\nAll IDs map to the same usernames. The ID-based fix was SAFE in this case.")
else:
    print("\nWARNING: ID mismatch detected! The fix may have linked Google accounts to WRONG users!")

pg_cur.close()
pg_conn.close()
