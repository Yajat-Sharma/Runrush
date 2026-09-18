import os
import sys
sys.path.insert(0, os.path.abspath('.'))
os.environ["DATABASE_URL"] = "sqlite:///test_reproduce.db"
os.environ["FLASK_ENV"] = "testing"

from app import app
from db import get_db

client = app.test_client()

# Seed database and log user in
with app.app_context():
    conn = get_db()
    with open("schema.sql") as f:
        conn.executescript(f.read())
    with open("migrations/002_seed_badges_challenges.sql") as f:
        conn.executescript(f.read())
    
    conn.execute("INSERT INTO users (id, username, pin) VALUES (1, 'testuser', '1234')")
    conn.commit()

# Mock login
with client.session_transaction() as sess:
    sess['user_id'] = 1

res = client.get('/api/badges')
print("STATUS CODE:", res.status_code)
if res.status_code != 200:
    print("ERROR:")
    print(res.get_data(as_text=True))
