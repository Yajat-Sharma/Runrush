import pytest
from flask import session
from app import app
from db import get_db
from datetime import datetime, timedelta
from extensions import bcrypt
import os

@pytest.fixture
def auth_client(client, app):
    app.config['LOGIN_ATTEMPT_WINDOW'] = 300
    app.config['MAX_LOGIN_ATTEMPTS'] = 5
    with app.app_context():
        conn = get_db()
        hashed_pin = bcrypt.generate_password_hash("123456")
        conn.execute(
            "INSERT INTO users (username, pin, failed_login_attempts) VALUES (?, ?, ?)",
            ("testuser", hashed_pin, 0)
        )
        conn.commit()
    return client

def test_brute_force_lockout(auth_client):
    # Try 4 wrong attempts
    for _ in range(4):
        response = auth_client.post('/login', data={'username': 'testuser', 'pin': '000000'})
        assert response.status_code == 200
        assert b'Invalid username or PIN' in response.data

    # 5th wrong attempt should lock the account
    response = auth_client.post('/login', data={'username': 'testuser', 'pin': '000000'})
    assert response.status_code == 200
    assert b'Account locked for 5 minutes' in response.data

    # 6th attempt (even with correct PIN) should be locked
    response = auth_client.post('/login', data={'username': 'testuser', 'pin': '123456'})
    assert response.status_code == 200
    assert b'Account locked. Try again in' in response.data

def test_successful_login_resets_attempts(auth_client):
    # Try 3 wrong attempts
    for _ in range(3):
        auth_client.post('/login', data={'username': 'testuser', 'pin': '000000'})
    
    with app.app_context():
        conn = get_db()
        attempts = conn.execute("SELECT failed_login_attempts FROM users WHERE username='testuser'").fetchone()[0]
        assert attempts == 3

    # Successful login
    response = auth_client.post('/login', data={'username': 'testuser', 'pin': '123456'})
    assert response.status_code == 302
    
    with app.app_context():
        conn = get_db()
        attempts = conn.execute("SELECT failed_login_attempts FROM users WHERE username='testuser'").fetchone()[0]
        assert attempts == 0

def test_security_headers(client):
    response = client.get('/login')
    assert response.headers.get('X-Content-Type-Options') == 'nosniff'
    assert response.headers.get('X-Frame-Options') == 'SAMEORIGIN'
    assert response.headers.get('X-XSS-Protection') == '1; mode=block'
    assert response.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'
    assert response.headers.get('Permissions-Policy') == 'geolocation=(), microphone=(), camera=()'
    assert 'Content-Security-Policy' in response.headers
    # Strict-Transport-Security should only be present if secure, but tests run on HTTP by default so it won't be present unless we mock request.is_secure

def test_session_inactivity_timeout(auth_client):
    # Login first
    auth_client.post('/login', data={'username': 'testuser', 'pin': '123456'})
    
    with auth_client.session_transaction() as sess:
        # Manually set last_active to 3 hours ago
        past_time = datetime.now() - timedelta(hours=3)
        sess['last_active'] = past_time.strftime("%Y-%m-%d %H:%M:%S")
        
    # Make a request to a protected route (dashboard or runs)
    # The before_request hook should clear the session and redirect
    response = auth_client.get('/runs')
    assert response.status_code == 302
    assert '/login?timeout=1' in response.headers['Location']
    
    with auth_client.session_transaction() as sess:
        assert 'user_id' not in sess
