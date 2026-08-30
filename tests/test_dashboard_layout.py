import json
import pytest
from app import app, get_db

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        with app.app_context():
            # Ensure table exists
            conn = get_db()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_dashboard_layout (
                    user_id INTEGER PRIMARY KEY,
                    layout_json TEXT NOT NULL
                )
            """)
            conn.commit()
            
            # Setup dummy user
            # Check if palak exists, or create one
            user = conn.execute("SELECT id FROM users WHERE username='test_dash_user'").fetchone()
            if not user:
                conn.execute("INSERT INTO users (username, pin, display_name) VALUES ('test_dash_user', 'hash', 'Test')")
                conn.commit()
            conn.close()
        yield client

def login(client, username):
    # Hack session manually since we just need the user_id
    with client.session_transaction() as sess:
        with app.app_context():
            conn = get_db()
            user = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            sess['user_id'] = user['id']

def test_get_default_dashboard_layout(client):
    login(client, 'test_dash_user')
    res = client.get('/api/dashboard-layout')
    assert res.status_code == 200
    layout = res.get_json()
    assert len(layout) == 4
    assert layout[0]['widget_type'] == 'leaderboard'
    assert layout[1]['widget_type'] == 'weekly_goal'

def test_post_dashboard_layout(client):
    login(client, 'test_dash_user')
    new_layout = [
        {"widget_type": "predicted_run", "visible": False},
        {"widget_type": "this_month", "visible": True}
    ]
    res = client.post('/api/dashboard-layout', json=new_layout)
    assert res.status_code == 200
    assert res.get_json() == {"success": True}
    
    # Verify it saved
    res2 = client.get('/api/dashboard-layout')
    layout = res2.get_json()
    assert len(layout) == 2
    assert layout[0]['widget_type'] == 'predicted_run'
    assert layout[0]['visible'] == False
    assert layout[0]['order'] == 0
    assert layout[1]['widget_type'] == 'this_month'
    assert layout[1]['visible'] == True
    assert layout[1]['order'] == 1

def test_post_dashboard_layout_invalid_widget(client):
    login(client, 'test_dash_user')
    new_layout = [
        {"widget_type": "hacked_widget", "visible": True}
    ]
    res = client.post('/api/dashboard-layout', json=new_layout)
    assert res.status_code == 400
    assert "Invalid widget_type" in res.get_json()['error']
