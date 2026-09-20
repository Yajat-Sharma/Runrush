import sqlite3
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv('DATABASE_URL')
if db_url and db_url.startswith('postgres'):
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    tables = [row[0] for row in cur.fetchall()]
    print('Postgres tables:', tables)
    if 'monthly_goals' not in tables:
        print('monthly_goals is missing!')
elif db_url:
    print('Using SQLite or other:', db_url)
    conn = sqlite3.connect(db_url.replace('sqlite:///', ''))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]
    print('SQLite tables:', tables)
    if 'monthly_goals' not in tables:
        print('monthly_goals is missing!')
else:
    print('No DATABASE_URL set')
