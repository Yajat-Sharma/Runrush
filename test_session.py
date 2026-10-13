import json
from datetime import datetime, timedelta
from app import app, init_db
from db import get_db

app.config['WTF_CSRF_ENABLED'] = False

with app.app_context():
    init_db()
    conn = get_db()
    conn.execute("DELETE FROM users WHERE username='session_user'")
    from extensions import bcrypt
    hashed_pin = bcrypt.generate_password_hash('123456')
    conn.execute("INSERT INTO users (username, pin) VALUES (?, ?)", ('session_user', hashed_pin))
    conn.commit()

with app.test_client() as client:
    # Login
    client.post('/login', data={'username': 'session_user', 'pin': '123456'})
    
    # Normal request
    resp1 = client.get('/runs')
    print("Valid session GET /runs status:", resp1.status_code)
    
    # Mutate data while valid
    resp2 = client.post('/api/weekly-goal', json={'goal_km': 10})
    print("Valid session API POST /api/weekly-goal status:", resp2.status_code)
    
    # Expire session manually
    with client.session_transaction() as sess:
        sess['last_active'] = (datetime.now() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
        
    # Normal request after expiration (should redirect)
    resp3 = client.get('/runs')
    print("Expired session GET /runs status:", resp3.status_code)
    
    # API request after expiration (should 401 JSON)
    resp4 = client.post('/api/weekly-goal', json={'goal_km': 20})
    print("Expired session API POST status:", resp4.status_code)
    print("Expired session API POST response:", resp4.data)
    
    # Verify mutation didn't occur
    with app.app_context():
        conn = get_db()
        goal = conn.execute("SELECT target_distance_km FROM weekly_goals JOIN users ON weekly_goals.user_id = users.id WHERE username='session_user'").fetchone()
        print(f"Goal after expired API request: {goal[0] if goal else None} (should be 10.0)")

