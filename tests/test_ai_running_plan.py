"""
Unit & Integration Tests for AI Running Plan Generator, Grilling Flow, and Home Screen Pinning.
"""

from datetime import datetime, timedelta

import pytest

from db import get_db
from services.goal_service import generate_ai_training_plan


@pytest.fixture
def plan_user_id(app):
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username = 'plan_runner'")
        conn.execute("INSERT INTO users (username, pin) VALUES ('plan_runner', '1234')")
        user = conn.execute("SELECT id FROM users WHERE username = 'plan_runner'").fetchone()
        u_id = user["id"]
        conn.commit()
        yield u_id

        conn.execute("DELETE FROM user_goals WHERE user_id = ?", (u_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (u_id,))
        conn.commit()
        conn.close()


def test_generate_ai_training_plan_structure(app, plan_user_id):
    """Verify AI plan generator produces structured roadmap with long runs and taper."""
    target_date = (datetime.now() + timedelta(weeks=8)).strftime("%Y-%m-%d")

    with app.app_context():
        plan = generate_ai_training_plan(
            user_id=plan_user_id,
            target_distance_km=10.0,
            target_date_str=target_date,
            days_per_week=3,
            fitness_level="intermediate",
            long_run_day="Sunday",
            race_name="Delhi 10K"
        )

    assert plan["status"] == "success"
    assert plan["total_weeks"] == 8
    assert len(plan["weeks"]) == 8
    assert plan["race_name"] == "Delhi 10K"
    assert plan["target_distance_km"] == 10.0
    assert plan["days_per_week"] == 3
    assert plan["is_feasible"] is True

    # Check that race week ends with RACE DAY of target distance
    race_week = plan["weeks"][-1]
    assert "Race Week" in race_week["phase"]
    race_workout = race_week["workouts"][-1]
    assert race_workout["distance_km"] == 10.0
    assert "RACE DAY" in race_workout["type"]

    # Verify coach notes are present
    assert len(plan["coach_notes"]) >= 3


def test_generate_ai_training_plan_half_marathon_taper(app, plan_user_id):
    """Verify 12-week Half Marathon includes 2-week taper."""
    target_date = (datetime.now() + timedelta(weeks=12)).strftime("%Y-%m-%d")

    with app.app_context():
        plan = generate_ai_training_plan(
            user_id=plan_user_id,
            target_distance_km=21.1,
            target_date_str=target_date,
            days_per_week=4,
            fitness_level="experienced",
            long_run_day="Sunday",
            race_name="Autumn Half"
        )

    assert plan["status"] == "success"
    assert plan["total_weeks"] == 12
    assert plan["taper_weeks"] == 2

    # Peak week should be before taper
    peak_week = plan["weeks"][9]  # Week 10
    assert "Peak" in peak_week["phase"]

    # Taper week should have reduced volume
    taper_week = plan["weeks"][10]  # Week 11
    assert "Taper" in taper_week["phase"]
    assert taper_week["long_run_km"] < peak_week["long_run_km"]


def test_api_goals_ai_generate_endpoint(client, auth_client):
    """Test POST /api/goals/ai-generate endpoint."""
    target_date = (datetime.now() + timedelta(weeks=8)).strftime("%Y-%m-%d")
    payload = {
        "target_distance_km": 5.0,
        "target_date": target_date,
        "days_per_week": 3,
        "fitness_level": "beginner",
        "long_run_day": "Sunday",
        "race_name": "Park 5K"
    }

    res = auth_client.post("/api/goals/ai-generate", json=payload)
    assert res.status_code == 200
    data = res.get_json()

    assert data["status"] == "success"
    assert data["target_distance_km"] == 5.0
    assert data["race_name"] == "Park 5K"
    assert len(data["weeks"]) == 8


def test_api_goals_ai_generate_mandatory_validations(client, auth_client):
    """Verify that baseless plan requests lacking mandatory fields are rejected with 400."""
    future_date = (datetime.now() + timedelta(weeks=6)).strftime("%Y-%m-%d")

    # 1. Missing target distance
    res1 = auth_client.post("/api/goals/ai-generate", json={
        "target_date": future_date,
        "long_run_day": "Sunday"
    })
    assert res1.status_code == 400
    assert "distance" in res1.get_json()["error"].lower()

    # 2. Missing target date
    res2 = auth_client.post("/api/goals/ai-generate", json={
        "target_distance_km": 10.0,
        "long_run_day": "Sunday"
    })
    assert res2.status_code == 400
    assert "date" in res2.get_json()["error"].lower()

    # 3. Target date in the past
    past_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    res3 = auth_client.post("/api/goals/ai-generate", json={
        "target_distance_km": 10.0,
        "target_date": past_date,
        "long_run_day": "Sunday"
    })
    assert res3.status_code == 400
    assert "future" in res3.get_json()["error"].lower()

    # 4. Missing preferred long run day
    res4 = auth_client.post("/api/goals/ai-generate", json={
        "target_distance_km": 10.0,
        "target_date": future_date
    })
    assert res4.status_code == 400
    assert "day" in res4.get_json()["error"].lower()


def test_create_and_pin_goal_to_home_screen(client, auth_client):
    """Test creating a plan with dashboard_pinned=True and verifying retrieval."""
    target_date = (datetime.now() + timedelta(weeks=8)).strftime("%Y-%m-%d")
    payload = {
        "goal_type": "race_plan",
        "target_distance_km": 10.0,
        "target_date": target_date,
        "days_per_week": 3,
        "dashboard_pinned": True,
        "race_name": "Winter 10K",
        "ai_plan": {
            "race_name": "Winter 10K",
            "total_weeks": 8,
            "coach_notes": ["Run smoothly!"]
        }
    }

    res = auth_client.post("/api/goals", json=payload)
    assert res.status_code == 200
    create_data = res.get_json()
    assert create_data["status"] == "success"

    # Fetch goals and verify dashboard_pinned is true and ai_plan is parsed
    get_res = auth_client.get("/api/goals")
    assert get_res.status_code == 200
    get_data = get_res.get_json()

    active_goal = next((g for g in get_data["goals"] if g["race_name"] == "Winter 10K"), None)
    assert active_goal is not None
    assert active_goal["dashboard_pinned"] is True
    assert active_goal["target_distance_km"] == 10.0
    assert active_goal["ai_plan"]["race_name"] == "Winter 10K"

    # Now test unpinning via POST /api/goals/<id>/pin
    pin_res = auth_client.post(f"/api/goals/{active_goal['id']}/pin", json={"pinned": False})
    assert pin_res.status_code == 200
    assert pin_res.get_json()["pinned"] is False

    # Verify unpinned in database
    get_res2 = auth_client.get("/api/goals")
    active_goal2 = next((g for g in get_res2.get_json()["goals"] if g["id"] == active_goal["id"]), None)
    assert active_goal2["dashboard_pinned"] is False


def test_inactive_plan_cancellation_and_notification(app, auth_client):
    """Test that plans inactive for 14+ days are cancelled and dispatch a notification."""
    import json

    from db import get_db
    from services.goal_service import check_and_cancel_inactive_goals

    # 1. Create an active goal simulated as created 20 days ago
    twenty_days_ago = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
    target_date = (datetime.now() + timedelta(weeks=8)).strftime("%Y-%m-%d")

    with app.app_context():
        conn = get_db()
        user_row = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        test_uid = user_row["id"]

        # Clean old test goals
        conn.execute("DELETE FROM user_goals WHERE user_id = ? AND race_name = 'Inactive Test Race'", (test_uid,))
        conn.commit()

        conn.execute(
            """INSERT INTO user_goals
               (user_id, goal_type, target_distance_km, target_date, days_per_week, status, dashboard_pinned, race_name, ai_plan_json, created_at)
               VALUES (?, 'race_plan', 10.0, ?, 3, 'active', 1, 'Inactive Test Race', ?, ?)
            """,
            (test_uid, target_date, json.dumps({"race_name": "Inactive Test Race", "weeks": []}), twenty_days_ago)
        )
        conn.commit()

        # 2. Run inactivity check with 14 days threshold
        cancelled = check_and_cancel_inactive_goals(user_id=test_uid, inactivity_days=14)
        assert len(cancelled) >= 1
        c_entry = next(c for c in cancelled if c["race_name"] == "Inactive Test Race")
        assert c_entry["days_inactive"] >= 20

        # 3. Check goal in database
        updated_goal = conn.execute(
            "SELECT status, dashboard_pinned, ai_plan_json FROM user_goals WHERE id = ?",
            (c_entry["goal_id"],)
        ).fetchone()
        assert updated_goal["status"] == "cancelled"
        assert not bool(updated_goal["dashboard_pinned"])
        plan_data = json.loads(updated_goal["ai_plan_json"])
        assert "cancellation_reason" in plan_data

        # 4. Check user notification was created
        notif_row = conn.execute(
            """SELECT n.title, n.message, n.type, un.user_id
               FROM user_notifications un
               JOIN notifications n ON un.notification_id = n.id
               WHERE un.user_id = ? AND n.type = 'PLAN_CANCELLED'
               ORDER BY n.id DESC LIMIT 1
            """,
            (test_uid,)
        ).fetchone()
        assert notif_row is not None
        assert "Training Plan Cancelled" in notif_row["title"]
        assert "Inactive Test Race" in notif_row["message"]

        # Clean up
        conn.execute("DELETE FROM user_goals WHERE id = ?", (c_entry["goal_id"],))
        conn.commit()


def test_api_goals_check_inactivity_endpoint(auth_client):
    """Test POST /api/goals/check-inactivity endpoint."""
    res = auth_client.post("/api/goals/check-inactivity", json={"inactivity_days": 14})
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "cancelled_count" in data
    assert "cancelled_goals" in data

