import pytest
from app import app
import db
import json

@pytest.fixture
def setup_users(app):
    with app.app_context():
        conn = db.get_db()
        # Create test admin
        conn.execute(
            "INSERT INTO users (id, username, pin, role, status) VALUES (?, ?, ?, ?, ?)",
            (1, "admin_user", "test", "admin", "active")
        )
        # Create standard user
        conn.execute(
            "INSERT INTO users (id, username, pin, role, status) VALUES (?, ?, ?, ?, ?)",
            (2, "normal_user", "test", "user", "active")
        )
        # Create blocked user
        conn.execute(
            "INSERT INTO users (id, username, pin, role, status) VALUES (?, ?, ?, ?, ?)",
            (3, "blocked_user", "test", "user", "blocked")
        )
        conn.commit()
        conn.close()


def login(client, user_id, username):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = username

def test_admin_can_create_notification(client, setup_users):
    login(client, 1, "admin_user")
    
    # 1. Create a notification for EVERYONE
    response = client.post('/api/admin/notifications', json={
        "title": "Welcome",
        "message": "Hello everyone!",
        "type": "SYSTEM",
        "audience_type": "EVERYONE"
    })
    assert response.status_code == 200
    assert response.get_json()["success"] == True
    
    # 2. Check if the normal_user got it
    login(client, 2, "normal_user")
    resp_user = client.get('/api/notifications/unread-count')
    assert resp_user.get_json()["count"] == 1

def test_blocked_users_do_not_get_everyone_notifications(client, setup_users):
    login(client, 1, "admin_user")
    client.post('/api/admin/notifications', json={
        "title": "Welcome",
        "message": "Hello everyone!",
        "type": "SYSTEM",
        "audience_type": "EVERYONE"
    })
    
    # Check if blocked_user got it
    login(client, 3, "blocked_user")
    resp_user = client.get('/api/notifications/unread-count')
    assert resp_user.get_json()["count"] == 0

def test_specific_user_notification(client, setup_users):
    login(client, 1, "admin_user")
    
    # Send specific notification to normal_user
    response = client.post('/api/admin/notifications', json={
        "title": "Just for you",
        "message": "Special promo",
        "type": "PROMO",
        "audience_type": "SPECIFIC_USER",
        "target_username": "normal_user"
    })
    assert response.status_code == 200
    
    # normal_user should have it
    login(client, 2, "normal_user")
    resp_user = client.get('/api/notifications/unread-count')
    assert resp_user.get_json()["count"] == 1
    
    # admin shouldn't have it (even though they are active, it was specifically for normal_user)
    login(client, 1, "admin_user")
    resp_admin = client.get('/api/notifications/unread-count')
    assert resp_admin.get_json()["count"] == 0

def test_mark_as_read(client, setup_users):
    # Setup
    login(client, 1, "admin_user")
    client.post('/api/admin/notifications', json={
        "title": "Alert",
        "message": "System going down",
        "type": "ALERT",
        "audience_type": "EVERYONE"
    })
    
    login(client, 2, "normal_user")
    
    # Fetch notifications to get the ID
    resp = client.get('/api/notifications')
    data = resp.get_json()
    assert len(data["notifications"]) == 1
    notif_id = data["notifications"][0]["id"]
    
    # Check unread count is 1
    assert client.get('/api/notifications/unread-count').get_json()["count"] == 1
    
    # Mark as read
    client.post(f'/api/notifications/{notif_id}/read')
    
    # Check unread count is 0
    assert client.get('/api/notifications/unread-count').get_json()["count"] == 0
    
    # Notification still exists but is read
    resp = client.get('/api/notifications')
    assert len(resp.get_json()["notifications"]) == 1

def test_normal_user_cannot_access_admin_endpoints(client, setup_users):
    login(client, 2, "normal_user")
    
    # Try to GET admin notifications page
    response = client.get('/admin/notifications')
    assert response.status_code == 403
    
    # Try to POST to admin notifications API
    response = client.post('/api/admin/notifications', json={
        "title": "Hacked",
        "message": "I'm sending this to everyone!",
        "type": "ALERT",
        "audience_type": "EVERYONE"
    })
    assert response.status_code == 403
