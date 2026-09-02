import pytest
import json
from datetime import datetime, timedelta

def test_weekly_goal_no_goal(auth_client):
    res = auth_client.get("/api/weekly-goal-progress")
    assert res.status_code == 200
    data = res.get_json()
    assert data["goal_km"] is None

def test_weekly_goal_set_and_update(auth_client):
    res = auth_client.post("/api/weekly-goal", json={"goal_km": -10})
    assert res.status_code == 400
    
    res = auth_client.post("/api/weekly-goal", json={"goal_km": 30.5})
    assert res.status_code == 200
    assert res.get_json()["success"] is True
    
    res = auth_client.get("/api/weekly-goal-progress")
    assert res.status_code == 200
    data = res.get_json()
    assert data["goal_km"] == 30.5
    assert data["current_km"] == 0
    assert data["percent_complete"] == 0
    
    auth_client.post("/api/weekly-goal", json={"goal_km": 50})
    res = auth_client.get("/api/weekly-goal-progress")
    assert res.get_json()["goal_km"] == 50

def test_weekly_goal_progress_calculation(auth_client, app):
    auth_client.post("/api/weekly-goal", json={"goal_km": 20})
    
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    run_date_str = week_start.strftime("%Y-%m-%d")
    
    from db import get_db
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (1, run_date_str, 10.0, 50, 5.0, 500)
        )
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (1, run_date_str, 5.0, 25, 5.0, 250)
        )
        conn.commit()
        conn.close()
    
    res = auth_client.get("/api/weekly-goal-progress")
    data = res.get_json()
    assert data["goal_km"] == 20
    assert data["current_km"] == 15.0
    assert data["percent_complete"] == 75.0
    
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (1, run_date_str, 10.0, 50, 5.0, 500)
        )
        conn.commit()
        conn.close()
    
    res = auth_client.get("/api/weekly-goal-progress")
    data = res.get_json()
    assert data["current_km"] == 25.0
    assert data["percent_complete"] == 100.0

def test_week_boundary_consistency(auth_client, app, monkeypatch):
    import app as my_app
    
    class MockDatetime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 8, 26, 12, 0, 0)
            
        @classmethod
        def utcnow(cls):
            return datetime(2026, 8, 26, 12, 0, 0)
        
        @classmethod
        def strptime(cls, *args, **kwargs):
            return datetime.strptime(*args, **kwargs)
    
    monkeypatch.setattr(my_app, "datetime", MockDatetime)
    import utils.dates
    monkeypatch.setattr(utils.dates, "datetime", MockDatetime)
    
    auth_client.post("/api/weekly-goal", json={"goal_km": 10})
    
    from db import get_db
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (1, "2026-08-24", 5.0, 25, 5.0, 250)
        )
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (1, "2026-08-30", 3.0, 15, 5.0, 150)
        )
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (1, "2026-08-23", 10.0, 50, 5.0, 500)
        )
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (1, "2026-08-31", 10.0, 50, 5.0, 500)
        )
        conn.commit()
        conn.close()
    
    res = auth_client.get("/api/weekly-goal-progress")
    data = res.get_json()
    assert data["current_km"] == 8.0
    
    res_lb = auth_client.get("/dashboard")
    html = res_lb.get_data(as_text=True)
    assert "8.00" in html
