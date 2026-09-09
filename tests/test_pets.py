import pytest
from datetime import datetime, timedelta
import os
import json

from db import get_db
from app import app
from services.pet_service import get_pet, adopt_pet, feed_pet, remove_km, evaluate_pet_health

@pytest.fixture
def setup_db(app):
    with app.app_context():
        conn = get_db()
        # Clean up users/runs/pets for test
        conn.execute("DELETE FROM user_pets")
        conn.execute("DELETE FROM runs WHERE user_id = (SELECT id FROM users WHERE username = 'pet_tester')")
        conn.execute("DELETE FROM users WHERE username = 'pet_tester'")
        
        conn.execute("INSERT INTO users (username, pin) VALUES ('pet_tester', '1234')")
        user = conn.execute("SELECT id FROM users WHERE username = 'pet_tester'").fetchone()
        user_id = user['id']
        
        conn.commit()
        yield user_id
        
        conn.execute("DELETE FROM user_pets WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM runs WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()

def test_pet_adoption_and_basic_feeding(setup_db):
    user_id = setup_db
    with app.app_context():
        # Adopt
        adopt_pet(user_id, "TestDog", "dog")
        pet = get_pet(user_id)
        assert pet is not None
        assert pet['level'] == 1
        assert pet['total_km_fed'] == 0
        assert pet['health_status'] == 'happy'
        
        # Feed 15km - should evolve to level 2 (threshold 10)
        feed_pet(user_id, 15.0, datetime.now().strftime("%Y-%m-%d"))
        pet = get_pet(user_id)
        assert pet['level'] == 2
        assert pet['total_km_fed'] == 15.0
        
        # Remove 10km - should devolve to level 1
        remove_km(user_id, 10.0)
        pet = get_pet(user_id)
        assert pet['level'] == 1
        assert pet['total_km_fed'] == 5.0

def test_pet_health_degradation(setup_db):
    user_id = setup_db
    with app.app_context():
        adopt_pet(user_id, "TestBird", "bird")
        
        # Manually set last_fed back by 4 days
        conn = get_db()
        past_date = (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d")
        conn.execute("UPDATE user_pets SET last_fed_date = ? WHERE user_id = ?", (past_date, user_id))
        conn.commit()
        conn.close()
        
        evaluate_pet_health(user_id)
        pet = get_pet(user_id)
        assert pet['health_status'] == 'sleepy'
        
        # Set back 8 days
        conn = get_db()
        past_date2 = (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d")
        conn.execute("UPDATE user_pets SET last_fed_date = ? WHERE user_id = ?", (past_date2, user_id))
        conn.commit()
        conn.close()
        
        evaluate_pet_health(user_id)
        pet = get_pet(user_id)
        assert pet['health_status'] == 'waiting for you'

def test_call_sites_integration(setup_db, client):
    user_id = setup_db
    
    # Login
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        
    with app.app_context():
        adopt_pet(user_id, "IntegrationDog", "dog")
    
    # 1. /add route
    client.post('/add', data={
        'date': datetime.now().strftime('%Y-%m-%d'),
        'distance': '5.0',
        'time': '30',
        'run_type': 'Easy'
    })
    
    with app.app_context():
        pet = get_pet(user_id)
        assert pet['total_km_fed'] == 5.0
        
    # 2. /api/sync-run
    client.post('/api/sync-run', json={
        'date': datetime.now().strftime('%Y-%m-%d'),
        'distance': 6.0,
        'time': 35,
        'tempId': 'sync-123'
    })
    
    with app.app_context():
        pet = get_pet(user_id)
        assert pet['total_km_fed'] == 11.0
        
    # 3. Strava Import (mock)
    client.post('/api/confirm-import', json={
        'runs': [
            {'date': datetime.now().strftime('%Y-%m-%d'), 'distance': 4.0, 'time': 20, 'run_type': 'Easy', 'notes': ''}
        ]
    })
    
    with app.app_context():
        pet = get_pet(user_id)
        assert pet['total_km_fed'] == 15.0
        
    # 4. Screenshot Import (mock)
    client.post('/api/confirm-screenshot-import', json={
        'date': datetime.now().strftime('%Y-%m-%d'),
        'distance_km': '3.0',
        'time_min': '15',
        'run_type': 'Easy',
        'notes': '',
        'source_app': 'Strava'
    })
    
    with app.app_context():
        pet = get_pet(user_id)
        assert pet['total_km_fed'] == 18.0
        
    # Test Edit Run
    # Find one of the runs
    with app.app_context():
        conn = get_db()
        run = conn.execute("SELECT id, distance_km FROM runs WHERE user_id = ? LIMIT 1", (user_id,)).fetchone()
        conn.close()
        
    run_id = run['id']
    old_dist = run['distance_km']
    
    # Edit down to 1.0
    client.post(f'/edit/{run_id}', data={
        'date': datetime.now().strftime('%Y-%m-%d'),
        'distance': '1.0',
        'time': '30'
    })
    
    with app.app_context():
        pet = get_pet(user_id)
        expected = 18.0 - old_dist + 1.0
        assert pet['total_km_fed'] == expected
        
    # Test Delete Run
    client.post(f'/delete/{run_id}')
    
    with app.app_context():
        pet = get_pet(user_id)
        assert pet['total_km_fed'] == expected - 1.0
