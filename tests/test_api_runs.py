import pytest
from datetime import datetime, timedelta
from models.user import User

def test_api_runs_auth_required(client):
    """1. /api/runs requires authentication."""
    resp = client.get('/api/runs')
    assert resp.status_code == 401
    assert resp.json["error"] == "Unauthorized"

def test_api_runs_data_isolation(client, app):
    """2. User A cannot receive User B's runs."""
    with app.app_context():
        from app import get_db
        conn = get_db()
        hashed_pin = User.hash_pin('1234')
        conn.execute("INSERT INTO users (username, pin) VALUES ('userA', ?), ('userB', ?)", (hashed_pin, hashed_pin))
        user_a = conn.execute("SELECT id FROM users WHERE username='userA'").fetchone()['id']
        user_b = conn.execute("SELECT id FROM users WHERE username='userB'").fetchone()['id']
        conn.execute("INSERT INTO runs (user_id, distance_km, time_min, pace, calories, date) VALUES (?, 5, 30, 6, 300, '2026-09-01')", (user_a,))
        conn.execute("INSERT INTO runs (user_id, distance_km, time_min, pace, calories, date) VALUES (?, 10, 60, 6, 600, '2026-09-02')", (user_b,))
        conn.commit()

    client.post('/login', data={'username': 'userA', 'pin': '1234'})
    resp = client.get('/api/runs')
    assert resp.status_code == 200
    runs = resp.json["runs"]
    assert len(runs) == 1
    assert runs[0]["distance_km"] == 5

def test_api_runs_pagination(client, app):
    """3, 4, 5, 6. Pagination offset and limits."""
    with app.app_context():
        from app import get_db
        conn = get_db()
        hashed_pin = User.hash_pin('1234')
        conn.execute("INSERT INTO users (username, pin) VALUES ('userC', ?)", (hashed_pin,))
        user_c = conn.execute("SELECT id FROM users WHERE username='userC'").fetchone()['id']
        for i in range(35):
            date_str = (datetime(2026, 9, 1) + timedelta(days=i)).strftime('%Y-%m-%d')
            conn.execute("INSERT INTO runs (user_id, distance_km, time_min, pace, calories, date) VALUES (?, ?, 30, 6, 300, ?)", (user_c, float(i), date_str))
        conn.commit()

    client.post('/login', data={'username': 'userC', 'pin': '1234'})
    
    resp1 = client.get('/api/runs?offset=0&limit=15&sort=date_asc')
    assert resp1.status_code == 200
    batch1 = resp1.json["runs"]
    assert len(batch1) == 15
    assert batch1[0]["distance_km"] == 0.0
    assert batch1[-1]["distance_km"] == 14.0

    resp2 = client.get('/api/runs?offset=15&limit=15&sort=date_asc')
    batch2 = resp2.json["runs"]
    assert len(batch2) == 15
    assert batch2[0]["distance_km"] == 15.0

    ids1 = {r["id"] for r in batch1}
    ids2 = {r["id"] for r in batch2}
    assert ids1.isdisjoint(ids2)

    resp3 = client.get('/api/runs?offset=30&limit=15&sort=date_asc')
    batch3 = resp3.json["runs"]
    assert len(batch3) == 5
    assert batch3[0]["distance_km"] == 30.0

def test_api_runs_invalid_params(client, app):
    """7. Invalid offset/limit are handled safely."""
    with app.app_context():
        from app import get_db
        conn = get_db()
        hashed_pin = User.hash_pin('1234')
        conn.execute("INSERT INTO users (username, pin) VALUES ('userD', ?)", (hashed_pin,))
        conn.commit()
    
    client.post('/login', data={'username': 'userD', 'pin': '1234'})
    
    resp = client.get('/api/runs?offset=abc')
    assert resp.status_code == 400

    resp = client.get('/api/runs?offset=-5')
    assert resp.status_code == 400

def test_api_runs_filter_sort(client, app):
    """8. Existing sort/filter behavior matches."""
    with app.app_context():
        from app import get_db
        conn = get_db()
        hashed_pin = User.hash_pin('1234')
        conn.execute("INSERT INTO users (username, pin) VALUES ('userE', ?)", (hashed_pin,))
        user_e = conn.execute("SELECT id FROM users WHERE username='userE'").fetchone()['id']
        
        conn.execute("INSERT INTO runs (user_id, distance_km, time_min, pace, calories, date) VALUES (?, 10, 60, 6, 600, '2026-09-01')", (user_e,))
        conn.execute("INSERT INTO runs (user_id, distance_km, time_min, pace, calories, date) VALUES (?, 5, 30, 6, 300, '2026-09-02')", (user_e,))
        conn.commit()

    client.post('/login', data={'username': 'userE', 'pin': '1234'})
    
    resp = client.get('/api/runs?sort=distance_desc')
    runs = resp.json["runs"]
    assert runs[0]["distance_km"] == 10
    assert runs[1]["distance_km"] == 5

    resp = client.get('/api/runs?filter=5k10k')
    assert len(resp.json["runs"]) == 2

def test_api_runs_can_retrieve_all(client, app):
    """9. A user with >30 runs can eventually retrieve every run."""
    with app.app_context():
        from app import get_db
        conn = get_db()
        hashed_pin = User.hash_pin('1234')
        conn.execute("INSERT INTO users (username, pin) VALUES ('userF', ?)", (hashed_pin,))
        user_f = conn.execute("SELECT id FROM users WHERE username='userF'").fetchone()['id']
        for i in range(100):
            conn.execute("INSERT INTO runs (user_id, distance_km, time_min, pace, calories, date) VALUES (?, 5, 30, 6, 300, '2026-09-01')", (user_f,))
        conn.commit()

    client.post('/login', data={'username': 'userF', 'pin': '1234'})
    
    offset = 0
    limit = 15
    total_loaded = 0
    
    while True:
        resp = client.get(f'/api/runs?offset={offset}&limit={limit}')
        batch = resp.json["runs"]
        if not batch:
            break
        total_loaded += len(batch)
        offset += limit
        
    assert total_loaded == 100
