import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv('DATABASE_URL')
conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'badges'")
cols = cur.fetchall()
print('badges columns:', cols)

cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'user_badges'")
cols = cur.fetchall()
print('user_badges columns:', cols)
