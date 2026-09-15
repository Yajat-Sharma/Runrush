import os
import sqlite3
import psycopg2
from dotenv import load_dotenv

load_dotenv()

SQLITE_PATH = "runs.db"
PG_URL = os.environ.get("DATABASE_URL")

print(f"Target DB: {PG_URL[:40]}...")

def fix_users():
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg2.connect(PG_URL)
    
    rows = sqlite_conn.execute("SELECT id, google_id, google_email, recovery_email, recovery_email_verified, bio, next_race FROM users").fetchall()
    
    pg_cur = pg_conn.cursor()
    count = 0
    for row in rows:
        user_id = row["id"]
        google_id = row["google_id"]
        google_email = row["google_email"]
        recovery_email = row["recovery_email"]
        recovery_email_verified = row["recovery_email_verified"]
        bio = row["bio"]
        next_race = row["next_race"]
        
        pg_cur.execute(
            """UPDATE users 
               SET google_id = %s, 
                   google_email = %s, 
                   recovery_email = %s, 
                   recovery_email_verified = %s, 
                   bio = %s, 
                   next_race = %s 
               WHERE id = %s""",
            (google_id, google_email, recovery_email, recovery_email_verified, bio, next_race, user_id)
        )
        count += 1

    pg_conn.commit()
    print(f"Updated {count} users with missing columns.")
    
    sqlite_conn.close()
    pg_conn.close()

if __name__ == "__main__":
    fix_users()
