import pytest
from datetime import datetime, timedelta
import math

from services.goal_service import check_goal_feasibility
from app import app
from db import get_db

@pytest.fixture
def setup_db(app):
    with app.app_context():
        conn = get_db()
        # Clean up users/runs for test
        conn.execute("DELETE FROM users WHERE username = 'goal_tester'")
        conn.execute("INSERT INTO users (username, pin) VALUES ('goal_tester', '1234')")
        user = conn.execute("SELECT id FROM users WHERE username = 'goal_tester'").fetchone()
        user_id = user['id']
        
        conn.commit()
        yield user_id
        
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.execute("DELETE FROM runs WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

def test_absurd_goal(setup_db):
    user_id = setup_db
    # 42km in 2 days should be rejected by Layer 1 (needs 16 weeks)
    today = datetime.now()
    target = (today + timedelta(days=2)).strftime("%Y-%m-%d")
    
    with app.app_context():
        is_feasible, reject_data = check_goal_feasibility(user_id, 42.0, target, 3)
        
    assert is_feasible is False
    assert reject_data is not None
    assert "Even Olympic athletes need more time" in reject_data['message'] or "That's a big jump" in reject_data['message']
    
    # Check suggested date is roughly 16 weeks from today
    suggested = datetime.strptime(reject_data['suggested_date'], "%Y-%m-%d")
    expected = today + timedelta(weeks=16)
    assert abs((suggested - expected).days) <= 1

def test_feasible_beginner_goal(setup_db):
    user_id = setup_db
    # 5km in 8 weeks, 3 days/week. Layer 1 needs 4 weeks. No history = beginner.
    today = datetime.now()
    target = (today + timedelta(weeks=8)).strftime("%Y-%m-%d")
    
    with app.app_context():
        is_feasible, reject_data = check_goal_feasibility(user_id, 5.0, target, 3)
        
    assert is_feasible is True
    assert reject_data is None

def test_borderline_experienced_goal(setup_db):
    user_id = setup_db
    today = datetime.now()
    target = (today + timedelta(weeks=4)).strftime("%Y-%m-%d")
    
    with app.app_context():
        # Inject run history
        conn = get_db()
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, (today - timedelta(days=2)).strftime("%Y-%m-%d"), 15.0, 90, 6.0, 1000, 'long', '', today.strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        
        # User has a 15k run recently. Wants to do 21k (Half marathon) in 4 weeks.
        # Layer 1 for 21k requires 10 weeks! So even though they are fit, it hits the hard floor.
        is_feasible, reject_data = check_goal_feasibility(user_id, 21.0, target, 3)
        
    assert is_feasible is False
    # Suggested date should be governed by Layer 1 = 10 weeks
    suggested = datetime.strptime(reject_data['suggested_date'], "%Y-%m-%d")
    expected = today + timedelta(weeks=10)
    assert abs((suggested - expected).days) <= 1
