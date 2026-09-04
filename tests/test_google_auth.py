import pytest
import os
from unittest.mock import patch, MagicMock

os.environ['GOOGLE_CLIENT_ID'] = 'mock-client-id'
os.environ['GOOGLE_CLIENT_SECRET'] = 'mock-client-secret'

from app import app, oauth
from db import get_db

@pytest.fixture
def client(app):
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for easier testing
    
    with app.test_client() as client:
        with app.app_context():
            # Setup DB with clean state
            conn = get_db()
            conn.execute("DELETE FROM users")
            conn.commit()
            
            # Setup some initial users
            conn.execute(
                "INSERT INTO users (username, pin, email, google_id, google_email) VALUES (?, ?, ?, ?, ?)",
                ("existing_google_user", "hashed_pin", "guser@example.com", "google_123", "guser@example.com")
            )
            
            conn.execute(
                "INSERT INTO users (username, pin, email) VALUES (?, ?, ?)",
                ("pin_only_user", "hashed_pin", "pinuser@example.com")
            )
            
            conn.execute(
                "INSERT INTO users (username, pin, email) VALUES (?, ?, ?)",
                ("testuser", "hashed_pin", "testuser@example.com")
            )
            
            conn.execute(
                "INSERT INTO users (username, pin, email, google_id) VALUES (?, ?, ?, ?)",
                ("other_linked_user", "hashed_pin", "other@example.com", "google_999")
            )
            
            conn.commit()
            conn.close()
        yield client

def mock_oauth_flow(mocker, mock_sub, mock_email):
    mock_token = {'userinfo': {'sub': mock_sub, 'email': mock_email}}
    mock_authorize = mocker.patch('app.oauth.google.authorize_access_token', return_value=mock_token)
    return mock_authorize


def test_google_login_existing_user(client, mocker):
    mock_oauth_flow(mocker, 'google_123', 'guser@example.com')
    
    with client.session_transaction() as sess:
        sess.clear()
        
    response = client.get('/auth/google/callback', follow_redirects=True)
    assert response.status_code == 200
    assert b'Dashboard' in response.data or b'RunRush' in response.data  # assuming redirect to index
    
    with client.session_transaction() as sess:
        assert sess['username'] == 'existing_google_user'

def test_google_login_new_user_forces_pin(client, mocker):
    mock_oauth_flow(mocker, 'google_new', 'newuser@example.com')
    
    with client.session_transaction() as sess:
        sess.clear()
        sess['intent'] = 'register'
        
    response = client.get('/auth/google/callback', follow_redirects=True)
    assert response.status_code == 200
    assert b'Secure your Account' in response.data
    
    with client.session_transaction() as sess:
        assert sess['username'] == 'newuser'
        
    # Verify DB state
    with app.app_context():
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username='newuser'").fetchone()
        assert user['google_id'] == 'google_new'
        assert user['pin'] == ''
        conn.close()

def test_google_login_email_collision(client, mocker):
    mock_oauth_flow(mocker, 'google_unlinked', 'pinuser@example.com')
    
    with client.session_transaction() as sess:
        sess.clear()
        sess['intent'] = 'register'
        
    response = client.get('/auth/google/callback', follow_redirects=True)
    assert response.status_code == 200
    assert b'An account already exists with this email.' in response.data
    
    # Should not be logged in
    with client.session_transaction() as sess:
        assert 'user_id' not in sess

def test_google_login_linking(client, mocker):
    mock_oauth_flow(mocker, 'google_linking', 'linkme@example.com')
    
    with app.app_context():
        conn = get_db()
        user_id = conn.execute("SELECT id FROM users WHERE username='testuser'").fetchone()['id']
        conn.close()

    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = 'testuser'
        sess['linking'] = True
        
    response = client.get('/auth/google/callback', follow_redirects=True)
    assert response.status_code == 200
    assert b'Google account successfully linked!' in response.data
    
    # Check DB
    with app.app_context():
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        assert user['google_id'] == 'google_linking'
        assert user['google_email'] == 'linkme@example.com'
        conn.close()

def test_google_login_username_collision(client, mocker):
    mock_oauth_flow(mocker, 'google_collision', 'testuser@otherdomain.com') # email prefix is 'testuser' which already exists
    
    with client.session_transaction() as sess:
        sess.clear()
        sess['intent'] = 'register'
        
    response = client.get('/auth/google/callback', follow_redirects=True)
    assert response.status_code == 200
    assert b'Secure your Account' in response.data
    
    with client.session_transaction() as sess:
        # should have generated a fallback username like 'testuser2'
        assert sess['username'] == 'testuser2'

def test_google_link_already_taken(client, mocker):
    # Try to link 'google_999' which belongs to 'other_linked_user'
    mock_oauth_flow(mocker, 'google_999', 'other@example.com')
    
    with app.app_context():
        conn = get_db()
        user_id = conn.execute("SELECT id FROM users WHERE username='testuser'").fetchone()['id']
        conn.close()

    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = 'testuser'
        sess['linking'] = True
        
    response = client.get('/auth/google/callback', follow_redirects=True)
    assert response.status_code == 200
    assert b'This Google account is already linked to another user.' in response.data

def test_google_disconnect(client):
    with app.app_context():
        conn = get_db()
        user_id = conn.execute("SELECT id FROM users WHERE username='existing_google_user'").fetchone()['id']
        conn.close()

    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = 'existing_google_user'
        
    response = client.post('/auth/google/disconnect', follow_redirects=True)
    assert response.status_code == 200
    assert b'Google account disconnected.' in response.data
    
    # check DB
    with app.app_context():
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        assert user['google_id'] is None
        conn.close()

def test_google_disconnect_lockout_prevention(client):
    # Create user with no PIN
    with app.app_context():
        conn = get_db()
        conn.execute("INSERT INTO users (username, pin, google_id) VALUES (?, ?, ?)", ("nopin_user", "", "google_nopin"))
        user_id = conn.execute("SELECT id FROM users WHERE username='nopin_user'").fetchone()['id']
        conn.commit()
        conn.close()
        
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = 'nopin_user'
        
    response = client.post('/auth/google/disconnect', follow_redirects=False)
    assert response.status_code == 302
    
    with client.session_transaction() as sess:
        flashes = dict(sess.get('_flashes', []))
        assert "You cannot disconnect your Google account because you don't have a backup PIN set. Please change your PIN first." in flashes.values()
    
    # check DB ensures still connected
    with app.app_context():
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        assert user['google_id'] == 'google_nopin'
        conn.close()
