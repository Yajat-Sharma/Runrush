from datetime import date

import app as app_module
from db import get_db
from services.monthly_report_service import build_monthly_report


def _user(client, username):
    client.post("/register", data={"username": username, "pin": "1234"})
    with client.application.app_context():
        return get_db().execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()["id"]


def _run(conn, user_id, date_value, distance, duration, pace):
    conn.execute(
        """INSERT INTO runs
           (user_id, date, distance_km, time_min, pace, calories)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, date_value, distance, duration, pace, distance * 60),
    )
    conn.commit()


def test_report_metrics_comparisons_and_duplicate_days(app, client):
    user_id = _user(client, "monthly_report_metrics")
    with app.app_context():
        conn = get_db()
        _run(conn, user_id, "2026-02-01", 5, 30, 6)
        _run(conn, user_id, "2026-02-01 18:00:00", 3, 18, 6)
        _run(conn, user_id, "2026-02-10", 10, 50, 5)
        _run(conn, user_id, "2026-01-15", 10, 60, 6)
        report = build_monthly_report(user_id, 2026, 2)

    metrics = report["metrics"]
    assert metrics["total_distance_km"] == 18
    assert metrics["run_count"] == 3
    assert metrics["average_pace_min_per_km"] == round(98 / 18, 2)
    assert metrics["longest_run_km"] == 10
    assert metrics["consistency_percentage"] == round(2 / 28 * 100, 1)
    assert metrics["best_run"]["pace_min_per_km"] == 5
    assert report["comparisons"]["total_distance_km"]["delta"] == 8


def test_report_handles_year_transition_and_zero_previous_distance(app, client):
    user_id = _user(client, "monthly_report_year")
    with app.app_context():
        conn = get_db()
        _run(conn, user_id, "2025-12-31", 5, 30, 6)
        _run(conn, user_id, "2026-01-10", 8, 48, 6)
        report = build_monthly_report(user_id, 2026, 1)

    assert report["previous_month"] == {"year": 2025, "month": 12, "has_data": True}
    assert report["comparisons"]["total_distance_km"]["percentage"] == 60.0


def test_monthly_report_prompt_retries_on_second_day_after_day_one_dismissal(app, client, monkeypatch):
    user_id = _user(client, "monthly_report_prompt")
    with app.app_context():
        _run(get_db(), user_id, "2026-01-10", 5, 30, 6)
    client.post("/login", data={"username": "monthly_report_prompt", "pin": "1234"})

    monkeypatch.setattr(app_module, "get_today", lambda: date(2026, 2, 1))
    assert client.get("/api/monthly-report/prompt").get_json()["available"] is True
    assert client.post("/api/monthly-report/action", json={"action": "dismiss"}).status_code == 200
    assert client.get("/api/monthly-report/prompt").get_json()["available"] is False

    monkeypatch.setattr(app_module, "get_today", lambda: date(2026, 2, 2))
    assert client.get("/api/monthly-report/prompt").get_json()["available"] is True
    client.post("/api/monthly-report/action", json={"action": "view"})
    assert client.get("/api/monthly-report/prompt").get_json()["available"] is False


def test_monthly_report_requires_authentication(client):
    assert client.get("/api/monthly-report/prompt").status_code == 401
    assert client.post("/api/monthly-report/action", json={"action": "view"}).status_code == 401
