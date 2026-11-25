"""
Unit and Integration Tests for Dynamic Workout Auto-Matcher & Check-off.
"""

from datetime import datetime, timedelta
import json
import pytest
from app import app
from db import get_db
from services.goal_service import (
    generate_ai_training_plan,
    match_run_to_training_plan,
    unmatch_run_from_training_plan,
    toggle_plan_workout_completion,
    reconcile_and_match_recent_runs_for_plan,
    evaluate_goals_for_user
)


@pytest.fixture
def matcher_user_data(app):
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username = 'matcher_runner'")
        conn.execute("INSERT INTO users (username, pin) VALUES ('matcher_runner', '1234')")
        user = conn.execute("SELECT id FROM users WHERE username = 'matcher_runner'").fetchone()
        u_id = user["id"]
        conn.commit()

        # Generate active plan 8 weeks out
        target_date = (datetime.now() + timedelta(weeks=8)).strftime("%Y-%m-%d")
        plan = generate_ai_training_plan(
            user_id=u_id,
            target_distance_km=10.0,
            target_date_str=target_date,
            days_per_week=3,
            fitness_level="intermediate",
            long_run_day="Sunday",
            race_name="Autumn 10K"
        )

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = conn.execute(
            """
            INSERT INTO user_goals (
                user_id, goal_type, target_distance_km, target_date, days_per_week,
                race_name, dashboard_pinned, status, ai_plan_json, created_at
            ) VALUES (?, 'race', ?, ?, ?, ?, 1, 'active', ?, ?)
            """,
            (
                u_id, 10.0, target_date, 3,
                "Autumn 10K", json.dumps(plan), now_str
            )
        )
        goal_id = cursor.lastrowid
        conn.commit()

        yield {"user_id": u_id, "goal_id": goal_id, "plan": plan}

        # Cleanup
        conn.execute("DELETE FROM runs WHERE user_id = ?", (u_id,))
        conn.execute("DELETE FROM user_goals WHERE user_id = ?", (u_id,))
        conn.execute("DELETE FROM user_notifications WHERE user_id = ?", (u_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (u_id,))
        conn.commit()
        conn.close()


def test_match_run_to_training_plan_success(app, matcher_user_data):
    """Test that a logged run matches scheduled workout and creates notification."""
    user_id = matcher_user_data["user_id"]
    goal_id = matcher_user_data["goal_id"]

    with app.app_context():
        conn = get_db()
        # Find the scheduled day of the first workout in week 1
        goal = conn.execute("SELECT ai_plan_json FROM user_goals WHERE id = ?", (goal_id,)).fetchone()
        plan = json.loads(goal["ai_plan_json"])
        w1_workout = plan["weeks"][0]["workouts"][0]
        wo_day = w1_workout["day"]
        planned_dist = w1_workout["distance_km"]

        # Calculate a date in week 1 that matches wo_day
        days_map = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
        today = datetime.now()
        day_offset = (days_map[wo_day] - today.weekday()) % 7
        target_run_date = (today + timedelta(days=day_offset)).strftime("%Y-%m-%d")

        # Insert a run on that day with matching distance + 0.3 km
        logged_dist = planned_dist + 0.3
        cur = conn.execute(
            "INSERT INTO runs (user_id, distance_km, time_min, pace, calories, date) VALUES (?, ?, 28.0, 5.5, 250.0, ?)",
            (user_id, logged_dist, target_run_date)
        )
        run_id = cur.lastrowid
        conn.commit()

        # Trigger matcher
        match_result = match_run_to_training_plan(
            user_id=user_id,
            run_id=run_id,
            distance_km=logged_dist,
            date_str=target_run_date
        )

        assert match_result is not None
        assert match_result["matched"] is True
        assert match_result["actual_km"] == round(logged_dist, 2)
        assert match_result["completed_count"] >= 1

        # Check updated goal in DB
        updated_goal = conn.execute("SELECT ai_plan_json FROM user_goals WHERE id = ?", (goal_id,)).fetchone()
        updated_plan = json.loads(updated_goal["ai_plan_json"])
        matched_wo = updated_plan["weeks"][0]["workouts"][0]
        assert matched_wo["completed"] is True
        assert matched_wo["completed_run_id"] == run_id
        assert matched_wo["completed_distance_km"] == round(logged_dist, 2)

        # Check in-app notification was delivered
        notif = conn.execute(
            "SELECT n.title, n.type FROM notifications n JOIN user_notifications un ON n.id = un.notification_id WHERE un.user_id = ?",
            (user_id,)
        ).fetchone()
        assert notif is not None
        assert notif["type"] == "WORKOUT_COMPLETED"
        assert "Workout Completed" in notif["title"]


def test_unmatch_run_from_training_plan(app, matcher_user_data):
    """Test unlinking a run reverts workout completion."""
    user_id = matcher_user_data["user_id"]
    goal_id = matcher_user_data["goal_id"]

    with app.app_context():
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO runs (user_id, distance_km, time_min, pace, calories, date) VALUES (?, 5.0, 25.0, 5.0, 250.0, ?)",
            (user_id, datetime.now().strftime("%Y-%m-%d"))
        )
        run_id = cur.lastrowid
        conn.commit()

        match_run_to_training_plan(user_id=user_id, run_id=run_id, distance_km=5.0)

        # Verify matched
        goal = conn.execute("SELECT ai_plan_json FROM user_goals WHERE id = ?", (goal_id,)).fetchone()
        plan = json.loads(goal["ai_plan_json"])
        assert any(wo.get("completed_run_id") == run_id for w in plan["weeks"] for wo in w["workouts"])

        # Unmatch
        reverted = unmatch_run_from_training_plan(user_id=user_id, run_id=run_id)
        assert reverted is True

        # Verify reverted in DB
        goal_after = conn.execute("SELECT ai_plan_json FROM user_goals WHERE id = ?", (goal_id,)).fetchone()
        plan_after = json.loads(goal_after["ai_plan_json"])
        assert not any(wo.get("completed_run_id") == run_id for w in plan_after["weeks"] for wo in w["workouts"])


def test_toggle_plan_workout_completion_manual(app, matcher_user_data):
    """Test manual workout toggle endpoint functionality."""
    user_id = matcher_user_data["user_id"]
    goal_id = matcher_user_data["goal_id"]

    with app.app_context():
        # Toggle check ON
        result_on = toggle_plan_workout_completion(
            user_id=user_id,
            goal_id=goal_id,
            week_number=1,
            workout_index=0
        )
        assert result_on is not None
        assert result_on["success"] is True
        assert result_on["workout"]["completed"] is True
        assert result_on["workout"]["manual_override"] is True
        assert result_on["completed_count"] == 1

        # Toggle check OFF
        result_off = toggle_plan_workout_completion(
            user_id=user_id,
            goal_id=goal_id,
            week_number=1,
            workout_index=0
        )
        assert result_off is not None
        assert result_off["success"] is True
        assert result_off["workout"]["completed"] is False
        assert result_off["completed_count"] == 0


def test_api_toggle_workout_endpoint_disabled(client, matcher_user_data):
    """Test POST /api/goals/<goal_id>/toggle-workout endpoint is disabled (403 Forbidden)."""
    user_id = matcher_user_data["user_id"]
    goal_id = matcher_user_data["goal_id"]

    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = "matcher_runner"

    # Call endpoint - manual check is prohibited, workouts only take inputs from registered runs
    res = client.post(
        f"/api/goals/{goal_id}/toggle-workout",
        json={"week_number": 1, "workout_index": 0}
    )
    assert res.status_code == 403
    data = res.get_json()
    assert data["status"] == "error"
    assert "Manual workout check-off is disabled" in data["message"]


def test_reconcile_and_match_recent_runs_flow(app, matcher_user_data):
    """Test scanning and auto-matching unlinked historical runs."""
    user_id = matcher_user_data["user_id"]
    goal_id = matcher_user_data["goal_id"]

    with app.app_context():
        conn = get_db()
        today_str = datetime.now().strftime("%Y-%m-%d")
        conn.execute(
            "INSERT INTO runs (user_id, distance_km, time_min, pace, calories, date) VALUES (?, 6.0, 32.0, 5.3, 300.0, ?)",
            (user_id, today_str)
        )
        conn.commit()

        # Reconcile unlinked runs
        matches = reconcile_and_match_recent_runs_for_plan(user_id=user_id)
        assert len(matches) >= 1
        assert matches[0]["matched"] is True

        # Subsequent run should not duplicate match
        matches_again = reconcile_and_match_recent_runs_for_plan(user_id=user_id)
        assert len(matches_again) == 0
