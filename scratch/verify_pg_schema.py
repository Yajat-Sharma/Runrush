import psycopg2
import sys

url = "postgresql://neondb_owner:npg_Bp2ZcLuge8HC@ep-rough-unit-awe9g4r7-pooler.c-12.us-east-1.aws.neon.tech/neondb?sslmode=require"

try:
    conn = psycopg2.connect(url)
    cur = conn.cursor()

    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    tables = [r[0] for r in cur.fetchall()]
    print("Tables:", tables)

    if '_yoyo_migration' in tables:
        cur.execute("SELECT migration_hash, migration_id, applied_at_utc FROM _yoyo_migration;")
        migrations = cur.fetchall()
        print("Migrations:", migrations)
        
        # Why is 004 missing?
        if 'monthly_goals' not in tables:
            print("Creating monthly_goals table...")
            cur.execute("""
            CREATE TABLE monthly_goals (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                target_km REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, year, month)
            );
            """)
            conn.commit()
            print("Table created.")

except Exception as e:
    print(e)
