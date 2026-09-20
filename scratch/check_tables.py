import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv('DATABASE_URL')
conn = psycopg2.connect(db_url)
cur = conn.cursor()

def check_table(t):
    cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)", (t,))
    return cur.fetchone()[0]

print('monthly_goals:', check_table('monthly_goals'))
print('user_pets:', check_table('user_pets'))
print('badges:', check_table('badges'))
print('user_badges:', check_table('user_badges'))
print('users:', check_table('users'))
print('runs:', check_table('runs'))
print('user_stats:', check_table('user_stats'))
