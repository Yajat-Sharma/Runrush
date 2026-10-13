import threading
import requests
import time
import os
os.environ['DATABASE_URL'] = 'sqlite:///test_runs.db'
from app import app, init_db
from db import get_db


app.config['WTF_CSRF_ENABLED'] = False

def setup_user():
    with app.app_context():
        init_db()
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username='concurrent_user'")
        from extensions import bcrypt
        hashed_pin = bcrypt.generate_password_hash('123456')
        conn.execute("INSERT INTO users (username, pin, failed_login_attempts) VALUES (?, ?, ?)", ('concurrent_user', hashed_pin, 0))
        conn.commit()

setup_user()

def login_attempt():
    with app.test_client() as client:
        client.post('/login', data={'username': 'concurrent_user', 'pin': '000000'})

threads = []
for i in range(10):
    t = threading.Thread(target=login_attempt)
    threads.append(t)
    t.start()

for t in threads:
    t.join()

with app.app_context():
    conn = get_db()
    user = conn.execute("SELECT failed_login_attempts, locked_until FROM users WHERE username='concurrent_user'").fetchone()
    print(f"Final failed attempts: {user['failed_login_attempts']}, Locked until: {user['locked_until']}")
