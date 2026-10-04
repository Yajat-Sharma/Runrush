
from app import app
from db import get_db
import os
import psycopg2

# Uses DATABASE_URL from the environment / .env (loaded by app) — never hard-code credentials

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = 2 # Yajat
    
    resp = client.get('/api/monthly-progress')
    print('Status:', resp.status_code)
    print('Data:', resp.data.decode())

