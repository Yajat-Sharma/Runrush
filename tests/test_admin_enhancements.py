import pytest
import os
from app import app
import db

@pytest.fixture
def client_app():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    
    with app.test_client() as client:
        with app.app_context():
            conn = db.get_db()
            # Clear tables
            conn.execute("DELETE FROM runs")
            conn.execute("DELETE FROM user_stats")
            conn.execute("DELETE FROM users")
            
            # Setup users for dev login testing
            conn.execute("INSERT INTO users (id, username, pin, role) VALUES (?, ?, ?, ?)", (1, "Yajat", "dummy", "admin"))
            conn.execute("INSERT INTO users (id, username, pin, role) VALUES (?, ?, ?, ?)", (2, "normal", "dummy", "user"))
            
            # Setup for statistics testing
            # User 1: Yajat (Admin) - 2 runs, 10.0 total km
            conn.execute("INSERT INTO runs (id, user_id, distance_km, time_min, pace, calories, date) VALUES (?, ?, ?, ?, ?, ?, ?)", (1, 1, 4.0, 30, "7:30", 300, "2026-09-01"))
            conn.execute("INSERT INTO runs (id, user_id, distance_km, time_min, pace, calories, date) VALUES (?, ?, ?, ?, ?, ?, ?)", (2, 1, 6.0, 45, "7:30", 450, "2026-09-02"))
            conn.execute("INSERT INTO user_stats (user_id, total_distance_km) VALUES (?, ?)", (1, 10.0))
            
            # User 2: normal (User) - 0 runs, 0.0 total km
            
            # User 3: active (User) - 1 run, 5.0 total km
            conn.execute("INSERT INTO users (id, username, pin, role) VALUES (?, ?, ?, ?)", (3, "active", "dummy", "user"))
            conn.execute("INSERT INTO runs (id, user_id, distance_km, time_min, pace, calories, date) VALUES (?, ?, ?, ?, ?, ?, ?)", (3, 3, 5.0, 40, "8:00", 350, "2026-09-03"))
            conn.execute("INSERT INTO user_stats (user_id, total_distance_km) VALUES (?, ?)", (3, 5.0))
            
            conn.commit()
            
        yield client, app

def login(client, username):
    with client.session_transaction() as sess:
        sess["user_id"] = 1 if username == "Yajat" else 2
        sess["username"] = username
        sess.permanent = True

# ---------------------------------------------------------
# DEV LOGIN TESTS
# ---------------------------------------------------------

def test_dev_login_disabled_by_default(client_app):
    client, app_obj = client_app
    app_obj.config['DEV_LOGIN_ENABLED'] = False
    
    resp = client.post('/dev-login')
    assert resp.status_code == 200
    assert b"Dev login is disabled" in resp.data
    
    with client.session_transaction() as sess:
        assert "user_id" not in sess

def test_dev_login_works_when_enabled(client_app):
    client, app_obj = client_app
    app_obj.config['DEV_LOGIN_ENABLED'] = True
    
    resp = client.post('/dev-login', follow_redirects=True)
    assert resp.status_code == 200
    
    with client.session_transaction() as sess:
        assert sess.get("username") == "Yajat"
        assert sess.get("user_id") == 1

# ---------------------------------------------------------
# ADMIN ACCESS TESTS
# ---------------------------------------------------------

def test_normal_user_cannot_access_admin(client_app):
    client, app_obj = client_app
    login(client, "normal")
    resp = client.get('/admin')
    assert resp.status_code == 403

def test_admin_can_access_dashboard(client_app):
    client, app_obj = client_app
    login(client, "Yajat")
    resp = client.get('/admin')
    assert resp.status_code == 200

# ---------------------------------------------------------
# USER STATISTICS TESTS
# ---------------------------------------------------------

def test_admin_dashboard_user_statistics(client_app):
    client, app_obj = client_app
    login(client, "Yajat")
    resp = client.get('/admin')
    assert resp.status_code == 200
    
    # We don't want to parse HTML rigidly, so let's check if the stats exist in the DB query directly
    with app_obj.app_context():
        conn = db.get_db()
        users_query = """
            WITH run_counts AS (
                SELECT user_id, COUNT(id) as total_runs
                FROM runs
                GROUP BY user_id
            )
            SELECT u.*, 
                   COALESCE(rc.total_runs, 0) as total_runs,
                   COALESCE(s.total_distance_km, 0.0) as total_km
            FROM users u
            LEFT JOIN run_counts rc ON u.id = rc.user_id
            LEFT JOIN user_stats s ON u.id = s.user_id
            ORDER BY u.id ASC
        """
        results = [dict(row) for row in conn.execute(users_query).fetchall()]
        
        # We expect exactly 3 rows, no duplicates
        assert len(results) == 3
        
        # Verify Yajat (User 1): 2 runs, 10.0 km
        yajat = results[0]
        assert yajat["username"] == "Yajat"
        assert yajat["total_runs"] == 2
        assert yajat["total_km"] == 10.0
        
        # Verify Normal (User 2): 0 runs, 0.0 km
        normal = results[1]
        assert normal["username"] == "normal"
        assert normal["total_runs"] == 0
        assert normal["total_km"] == 0.0
        
        # Verify Active (User 3): 1 run, 5.0 km
        active = results[2]
        assert active["username"] == "active"
        assert active["total_runs"] == 1
        assert active["total_km"] == 5.0
