from datetime import date
from pathlib import Path

import pytest

import app as app_module
from db import get_db
from services.monthly_report_service import build_monthly_report


def _user(client, username):
    client.post("/register", data={"username": username, "pin": "1234"})
    with client.application.app_context():
        return get_db().execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]


def _run(conn, user_id, date_value, distance, duration, pace):
    conn.execute(
        """INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, date_value, distance, duration, pace, distance * 60),
    )
    conn.commit()


@pytest.mark.parametrize("today, expected, is_live", [
    (date(2026, 10, 30), (2026, 10), True),
    (date(2026, 10, 31), (2026, 10), True),
    (date(2026, 11, 1), (2026, 10), False),
    (date(2026, 11, 2), (2026, 10), False),
    (date(2026, 11, 3), None, None),
    (date(2026, 11, 29), (2026, 11), True),
    (date(2026, 11, 30), (2026, 11), True),
    (date(2026, 12, 1), (2026, 11), False),
    (date(2026, 2, 27), (2026, 2), True),
    (date(2026, 2, 28), (2026, 2), True),
    (date(2024, 2, 28), (2024, 2), True),
    (date(2024, 2, 29), (2024, 2), True),
])
def test_monthly_report_window_handles_month_lengths_and_rollover(today, expected, is_live):
    result = app_module._monthly_report_window(today)
    assert (result[:2] if result else None) == expected
    assert (result[2] if result else None) == is_live


def test_report_calculates_weighted_metrics_and_previous_month_comparison(app, client):
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
    assert report["is_live"] is False


def test_live_report_includes_runs_through_today_but_not_future_dates(app, client):
    user_id = _user(client, "monthly_report_live")
    with app.app_context():
        conn = get_db()
        _run(conn, user_id, "2026-10-29", 5, 30, 6)
        _run(conn, user_id, "2026-10-30 18:00:00", 3, 18, 6)
        _run(conn, user_id, "2026-10-31", 9, 45, 5)
        report = build_monthly_report(user_id, 2026, 10, as_of_date=date(2026, 10, 30), is_live=True)

    assert report["metrics"]["run_count"] == 2
    assert report["metrics"]["total_distance_km"] == 8
    assert report["data_through"] == "2026-10-30"
    assert report["is_live"] is True


def test_report_recalculates_and_picks_up_runs_added_during_grace_days(app, client):
    user_id = _user(client, "monthly_report_refresh")
    with app.app_context():
        conn = get_db()
        _run(conn, user_id, "2026-10-10", 5, 30, 6)
        first = build_monthly_report(user_id, 2026, 10)
        _run(conn, user_id, "2026-10-30", 7, 35, 5)
        refreshed = build_monthly_report(user_id, 2026, 10)

    assert first["metrics"]["total_distance_km"] == 5
    assert refreshed["metrics"]["total_distance_km"] == 12
    assert refreshed["metrics"]["run_count"] == 2


def test_report_without_runs_returns_zero_metrics(app, client):
    user_id = _user(client, "monthly_report_empty")
    with app.app_context():
        report = build_monthly_report(user_id, 2026, 4)
    assert report["has_activity"] is False
    assert report["metrics"]["total_distance_km"] == 0
    assert report["metrics"]["run_count"] == 0
    assert report["metrics"]["average_pace_min_per_km"] is None
    assert report["metrics"]["best_run"] is None


def test_best_run_ignores_sub_kilometer_gps_noise(app, client):
    user_id = _user(client, "monthly_report_best")
    with app.app_context():
        conn = get_db()
        _run(conn, user_id, "2026-05-01", 0.25, 1, 4)
        _run(conn, user_id, "2026-05-02", 1.0, 7, 7)
        report = build_monthly_report(user_id, 2026, 5)
    assert report["metrics"]["best_run"]["distance_km"] == 1


def test_monthly_prompt_is_recalculated_each_open_and_maybe_later_has_no_state(app, client, monkeypatch):
    user_id = _user(client, "monthly_report_prompt")
    with app.app_context():
        _run(get_db(), user_id, "2026-10-10", 5, 30, 6)
    client.post("/login", data={"username": "monthly_report_prompt", "pin": "1234"})
    monkeypatch.setattr(app_module, "_monthly_report_today_from_request", lambda: date(2026, 10, 30))

    first = client.get("/api/monthly-report/prompt?timezone=Asia%2FKolkata").get_json()
    with app.app_context():
        _run(get_db(), user_id, "2026-10-30", 7, 35, 5)
    second = client.get("/api/monthly-report/prompt").get_json()

    assert first["available"] is True
    assert first["report"]["is_live"] is True
    assert second["report"]["metrics"]["total_distance_km"] == 12


def test_popup_opt_out_is_persistent_and_settings_can_reenable(app, client, monkeypatch):
    _user(client, "monthly_report_optout")
    client.post("/login", data={"username": "monthly_report_optout", "pin": "1234"})
    monkeypatch.setattr(app_module, "_monthly_report_today_from_request", lambda: date(2026, 11, 1))

    assert client.get("/api/monthly-report/prompt").get_json()["available"] is True
    saved = client.post("/api/monthly-report/action", json={"action": "opt_out"})
    assert saved.get_json()["popup_enabled"] is False
    assert client.get("/api/monthly-report/prompt").get_json()["available"] is False
    settings = client.get("/settings").get_data(as_text=True)
    assert 'id="monthlyReportPopupToggle"' in settings
    assert 'id="monthlyReportPopupToggle" name="monthly_report_popup_enabled" class="toggle-input" value="1" >' in settings

    client.post("/settings/monthly-report-preferences", data={"monthly_report_popup_enabled": "1"})
    assert client.get("/api/monthly-report/prompt").get_json()["available"] is True


def test_view_does_not_suppress_popup_and_detailed_report_is_accessible(app, client, monkeypatch):
    _user(client, "monthly_report_view")
    client.post("/login", data={"username": "monthly_report_view", "pin": "1234"})
    monkeypatch.setattr(app_module, "_monthly_report_today_from_request", lambda: date(2026, 11, 2))

    assert client.get("/api/monthly-report/prompt").get_json()["available"] is True
    page = client.get("/monthly-report?year=2026&month=10&timezone=Asia%2FKolkata")
    assert page.status_code == 200
    assert b"Finalised month" in page.data
    assert client.get("/api/monthly-report/prompt").get_json()["available"] is True


def test_monthly_report_requires_authentication(client):
    assert client.get("/api/monthly-report/prompt").status_code == 401
    assert client.post("/api/monthly-report/action", json={"action": "opt_out"}).status_code == 401
    assert client.get("/monthly-report?year=2026&month=10").status_code == 302


def test_timezone_validation_falls_back_safely(app, monkeypatch):
    monkeypatch.setattr(app_module, "get_today", lambda: date(2026, 10, 30))
    assert app_module._monthly_report_timezone("Asia/Kolkata").key == "Asia/Kolkata"
    assert app_module._monthly_report_local_today("not-a-timezone") == date(2026, 10, 30)
    assert app_module._monthly_report_local_today("not-a-timezone", "2026-11-01") == date(2026, 11, 1)


def test_popup_frontend_has_repeatable_later_and_persistent_opt_out_actions():
    root = Path(__file__).resolve().parents[1]
    template = (root / "templates" / "index.html").read_text(encoding="utf-8")
    script = (root / "static" / "js" / "monthly-report.js").read_text(encoding="utf-8")
    assert 'id="monthlyReportView"' in template and "View Monthly Report" in template
    assert 'id="monthlyReportLater"' in template and "Maybe Later" in template
    assert 'id="monthlyReportOptOut"' in template and "Don't show this again" in template
    assert "$('monthlyReportLater').addEventListener('click', hide)" in script
    assert "window.location.assign(`/monthly-report?${params.toString()}`)" in script
    assert "body: JSON.stringify({action: 'opt_out'})" in script
    assert "local_date: localDate" in script
