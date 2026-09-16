import os
from dotenv import load_dotenv
load_dotenv()

from app import app
from db import get_db
import json

with app.test_client() as client:
    print('Testing login page...')
    resp = client.get('/login')
    print(f'Login GET: {resp.status_code}')

    # Try to find a user in DB to test login
    with app.app_context():
        conn = get_db()
        user = conn.execute('SELECT username FROM users ORDER BY id LIMIT 1').fetchone()
        if user:
            print(f'User found: {user["username"]}, trying to hit dashboard as this user in session (mocked if possible)')

    # Just hit the APIs that do not require login, or simulate login if we can't
    # Actually, we can use client.post('/login') if we know a pin, but we don't.
    # But wait, we can just login directly by setting session cookie if we are a test client.
    with client.session_transaction() as sess:
        sess['user_id'] = 2 # Assuming Yajat is ID 2 based on previous output
    
    print('Testing dashboard as user 2...')
    resp = client.get('/')
    print(f'Dashboard GET: {resp.status_code}')
    
    print('Testing Analytics API...')
    resp = client.get('/api/analytics/insights')
    print(f'Analytics Insights GET: {resp.status_code}')

    print('Testing Runs API...')
    resp = client.get('/api/runs')
    print(f'Runs GET: {resp.status_code}')
    
    print('Testing Profile page...')
    resp = client.get('/profile')
    print(f'Profile GET: {resp.status_code}')
    
    print('Testing Leaderboard page...')
    resp = client.get('/social')
    print(f'Leaderboard GET: {resp.status_code}')

