import pytest
from datetime import datetime, timedelta
import calendar
from app import app
from db import get_db

@pytest.fixture
def setup_db(app, client):
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username IN ('user1', 'user2')")
        conn.commit()
        
        client.post('/register', data={'username': 'user1', 'pin': '1234'})
        client.post('/register', data={'username': 'user2', 'pin': '1234'})
        
        user1 = conn.execute("SELECT id FROM users WHERE username = 'user1'").fetchone()['id']
        user2 = conn.execute("SELECT id FROM users WHERE username = 'user2'").fetchone()['id']
        
        yield user1, user2
        
        conn.execute("DELETE FROM monthly_goals WHERE user_id IN (?, ?)", (user1, user2))
        conn.execute("DELETE FROM runs WHERE user_id IN (?, ?)", (user1, user2))
        conn.execute("DELETE FROM users WHERE username IN ('user1', 'user2')")
        conn.commit()
        conn.close()

def test_monthly_goals_crud(client, setup_db):
    user1, _ = setup_db
    
    # Login User 1
    client.post('/login', data={'username': 'user1', 'pin': '1234'})
    
    # 1. No goal initially
    now = datetime.now()
    res = client.get(f'/api/monthly-progress?year={now.year}&month={now.month}')
    assert res.status_code == 200
    data = res.json
    assert data["target_km"] is None
    
    # 2. Create goal
    res = client.post('/api/monthly-goals', json={'year': now.year, 'month': now.month, 'target_km': 50})
    assert res.status_code == 200
    
    res = client.get(f'/api/monthly-progress?year={now.year}&month={now.month}')
    assert res.json["target_km"] == 50.0
    
    # 3. Update goal
    res = client.post('/api/monthly-goals', json={'year': now.year, 'month': now.month, 'target_km': 75.5})
    assert res.status_code == 200
    
    res = client.get(f'/api/monthly-progress?year={now.year}&month={now.month}')
    assert res.json["target_km"] == 75.5
    
    # 4. Delete goal
    res = client.post('/api/monthly-goals', json={'year': now.year, 'month': now.month, 'target_km': ""})
    assert res.status_code == 200
    
    res = client.get(f'/api/monthly-progress?year={now.year}&month={now.month}')
    assert res.json["target_km"] is None

def test_monthly_progress_stats(client, setup_db):
    user1, _ = setup_db
    client.post('/login', data={'username': 'user1', 'pin': '1234'})
    
    now = datetime.now()
    year = now.year
    month = now.month
    
    client.post('/api/monthly-goals', json={'year': year, 'month': month, 'target_km': 10})
    
    res = client.get(f'/api/monthly-progress?year={year}&month={month}')
    assert res.json["run_count"] == 0
    assert res.json["total_distance"] == 0
    
    date_str = f"{year}-{month:02d}-15 10:00:00"
    with app.app_context():
        conn = get_db()
        conn.execute("INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
                     (user1, date_str, 5, 30, 6.0, 300))
        conn.commit()
    
    res = client.get(f'/api/monthly-progress?year={year}&month={month}')
    assert res.json["run_count"] == 1
    assert res.json["total_distance"] == 5.0
    
    with app.app_context():
        conn = get_db()
        conn.execute("INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
                     (user1, f"{year}-{month:02d}-16 10:00:00", 6, 30, 5.0, 350))
        conn.commit()
    
    res = client.get(f'/api/monthly-progress?year={year}&month={month}')
    assert res.json["run_count"] == 2
    assert res.json["total_distance"] == 11.0
    
    # Test Future Month
    future_year = year + 1
    res = client.get(f'/api/monthly-progress?year={future_year}&month={month}')
    assert res.json["run_count"] == 0
    assert res.json["total_distance"] == 0

def test_multiple_user_isolation(client, setup_db):
    user1, user2 = setup_db
    now = datetime.now()
    
    # User 1 Sets Goal
    client.post('/login', data={'username': 'user1', 'pin': '1234'})
    client.post('/api/monthly-goals', json={'year': now.year, 'month': now.month, 'target_km': 50})
    client.get('/logout')
    
    # User 2 Sets Goal
    client.post('/login', data={'username': 'user2', 'pin': '1234'})
    client.post('/api/monthly-goals', json={'year': now.year, 'month': now.month, 'target_km': 100})
    
    res = client.get(f'/api/monthly-progress?year={now.year}&month={now.month}')
    assert res.json["target_km"] == 100.0
    
    # Attempt to spoof using user_id
    client.post('/api/monthly-goals', json={'user_id': user1, 'year': now.year, 'month': now.month, 'target_km': 150})
    
    client.get('/logout')
    
    # Check User 1 goal is untouched
    client.post('/login', data={'username': 'user1', 'pin': '1234'})
    res = client.get(f'/api/monthly-progress?year={now.year}&month={now.month}')
    assert res.json["target_km"] == 50.0
