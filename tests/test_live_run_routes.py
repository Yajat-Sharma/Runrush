import pytest
from models.user import User
from app import get_db

def test_run_route_requires_auth(client):
    """Route endpoints require authentication."""
    resp = client.get('/api/run/1/route')
    assert resp.status_code == 401

    resp = client.post('/api/run/1/route', json={'route': [{'lat': 20, 'lng': 77}]})
    assert resp.status_code == 401

def test_save_and_get_run_route(client, app):
    """User can save and retrieve a GPS route for their run."""
    with app.app_context():
        conn = get_db()
        hashed_pin = User.hash_pin('1234')
        conn.execute("INSERT INTO users (username, pin) VALUES ('routeRunner', ?)", (hashed_pin,))
        user_id = conn.execute("SELECT id FROM users WHERE username='routeRunner'").fetchone()['id']
        conn.execute(
            "INSERT INTO runs (user_id, distance_km, time_min, pace, calories, date) VALUES (?, 5.0, 30.0, 6.0, 300, '2026-09-01')",
            (user_id,)
        )
        run_id = conn.execute("SELECT id FROM runs WHERE user_id = ?", (user_id,)).fetchone()['id']
        conn.commit()

    client.post('/login', data={'username': 'routeRunner', 'pin': '1234'})

    sample_route = [
        {'lat': 28.6139, 'lng': 77.2090, 'ts': 1690000000000},
        {'lat': 28.6145, 'lng': 77.2095, 'ts': 1690000010000},
    ]

    # Save route
    post_resp = client.post(f'/api/run/{run_id}/route', json={
        'route': sample_route,
        'total_distance_km': 5.0
    })
    assert post_resp.status_code == 200
    assert post_resp.json['ok'] is True

    # Retrieve route
    get_resp = client.get(f'/api/run/{run_id}/route')
    assert get_resp.status_code == 200
    data = get_resp.json
    assert len(data['route']) == 2
    assert data['total_distance_km'] == 5.0
    assert data['route'][0]['lat'] == 28.6139

def test_route_isolation_between_users(client, app):
    """User B cannot fetch User A's route."""
    with app.app_context():
        conn = get_db()
        hashed_pin = User.hash_pin('1234')
        conn.execute("INSERT INTO users (username, pin) VALUES ('runnerA', ?), ('runnerB', ?)", (hashed_pin, hashed_pin))
        user_a = conn.execute("SELECT id FROM users WHERE username='runnerA'").fetchone()['id']
        user_b = conn.execute("SELECT id FROM users WHERE username='runnerB'").fetchone()['id']
        conn.execute(
            "INSERT INTO runs (user_id, distance_km, time_min, pace, calories, date) VALUES (?, 3.0, 20.0, 6.6, 200, '2026-09-02')",
            (user_a,)
        )
        run_a = conn.execute("SELECT id FROM runs WHERE user_id = ?", (user_a,)).fetchone()['id']
        conn.commit()

    # User A saves route
    client.post('/login', data={'username': 'runnerA', 'pin': '1234'})
    client.post(f'/api/run/{run_a}/route', json={'route': [{'lat': 10, 'lng': 10}], 'total_distance_km': 3.0})

    # User B logs in and tries to access User A's route
    client.post('/login', data={'username': 'runnerB', 'pin': '1234'})
    resp = client.get(f'/api/run/{run_a}/route')
    assert resp.status_code == 404
