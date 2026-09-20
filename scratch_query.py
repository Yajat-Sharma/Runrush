import psycopg2
import sys
import os

neon_url = "postgresql://neondb_owner:npg_QnL41MkIWEzZ@ep-dark-term-b5ajazfp-pooler.c-7.us-east-2.aws.neon.tech/neondb?channel_binding=require&sslmode=require"

def check_db(url, name):
    print(f"--- Checking {name} ---")
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        
        cur.execute("SELECT current_database(), current_schema()")
        db, schema = cur.fetchone()
        print(f"Database: {db}, Schema: {schema}")
        
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'")
        cols = [r[0] for r in cur.fetchall()]
        print(f"users columns: {cols}")
        
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'monthly_goals'")
        mcols = [r[0] for r in cur.fetchall()]
        print(f"monthly_goals exists: {len(mcols) > 0}")
        if mcols:
            print(f"monthly_goals columns: {mcols}")
            
        cur.execute("SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'monthly_goals'::regclass")
        cons = cur.fetchall()
        print("monthly_goals constraints:")
        for c in cons:
            print(f" - {c[0]}: {c[1]}")
            
        cur.execute("SELECT migration_hash, migration_id, applied_at_utc FROM _yoyo_migration")
        yoyo = cur.fetchall()
        print(f"Yoyo migrations applied: {[y[1] for y in yoyo]}")
        
        # Test queries
        try:
            cur.execute("SELECT id, username, display_name, profile_emoji FROM users WHERE LOWER(username) = LOWER('Yajat')")
            print("Public Profile query succeeded")
        except Exception as e:
            print(f"Public Profile query failed: {e}")
            conn.rollback()
            
        try:
            cur.execute("SELECT id, user_id, year, month, target_km FROM monthly_goals WHERE user_id = 1 AND year = 2026 AND month = 9")
            print("Monthly Progress query succeeded")
        except Exception as e:
            print(f"Monthly Progress query failed: {e}")
            conn.rollback()
            
    except Exception as e:
        print(f"Error checking {name}: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

check_db(neon_url, "Neon PostgreSQL")
