"""
Tests for POST /api/trigger-monthly-emails and the /settings/email
monthly-summary opt-in checkbox. No real Resend calls: _post_to_resend
is monkeypatched, same as tests/test_monthly_summary_delivery.py.
"""

import pytest

from app import app
from db import get_db
import services.monthly_summary_delivery as delivery_mod


@pytest.fixture
def setup_user(app, client):
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username = 'eu1'")
        conn.commit()

        client.post('/register', data={'username': 'eu1', 'pin': '1234'})
        uid = conn.execute("SELECT id FROM users WHERE username = 'eu1'").fetchone()['id']
        conn.execute("UPDATE users SET email = 'eu1@example.com', email_monthly_summary = 1 WHERE id = ?", (uid,))
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "2026-05-10", 5.0, 25.0, 5.0, 350),
        )
        conn.commit()

        yield uid

        conn.execute("DELETE FROM monthly_summary_deliveries WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM runs WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM users WHERE username = 'eu1'")
        conn.commit()
        conn.close()


@pytest.fixture
def no_op_send(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setattr(delivery_mod, "_post_to_resend", lambda *a, **kw: (True, None))


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------

def test_cron_secret_auth_succeeds(client, setup_user, no_op_send, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cr3t")
    res = client.post(
        '/api/trigger-monthly-emails',
        json={"year": 2026, "month": 5},
        headers={"Authorization": "Bearer s3cr3t"},
    )
    assert res.status_code == 200
    assert res.json["success"] is True


def test_wrong_cron_secret_is_unauthorized(client, setup_user, no_op_send, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cr3t")
    res = client.post(
        '/api/trigger-monthly-emails',
        json={"year": 2026, "month": 5},
        headers={"Authorization": "Bearer wrong-guess"},
    )
    assert res.status_code == 401


def test_no_auth_at_all_is_forbidden(client, setup_user, no_op_send, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cr3t")
    res = client.post('/api/trigger-monthly-emails', json={"year": 2026, "month": 5})
    assert res.status_code == 403


def test_admin_session_auth_succeeds(client, app, setup_user, no_op_send, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cr3t")
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username = 'mm_admin'")
        conn.commit()
    client.post('/register', data={'username': 'mm_admin', 'pin': '9999'})
    with app.app_context():
        conn = get_db()
        conn.execute("UPDATE users SET role = 'admin' WHERE username = 'mm_admin'")
        conn.commit()
    client.post('/login', data={'username': 'mm_admin', 'pin': '9999'})

    # The admin-session fallback path calls csrf.protect() unconditionally
    # (mirrors /api/trigger-weekly-emails), so a real token is required even
    # though WTF_CSRF_ENABLED=False disables *automatic* form validation.
    # Pull one from the admin page's <meta name="csrf-token"> the same way
    # a real admin browser session would.
    admin_page = client.get('/admin')
    import re as _re
    token = _re.search(r'name="csrf-token" content="([^"]+)"', admin_page.get_data(as_text=True)).group(1)

    res = client.post(
        '/api/trigger-monthly-emails',
        json={"year": 2026, "month": 5},
        headers={"X-CSRFToken": token},
    )
    assert res.status_code == 200

    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username = 'mm_admin'")
        conn.commit()
        conn.close()


def test_non_admin_session_is_forbidden(client, app, setup_user, no_op_send, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cr3t")
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username = 'mm_plain'")
        conn.commit()
    client.post('/register', data={'username': 'mm_plain', 'pin': '9999'})
    client.post('/login', data={'username': 'mm_plain', 'pin': '9999'})

    res = client.post('/api/trigger-monthly-emails', json={"year": 2026, "month": 5})
    assert res.status_code == 403

    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username = 'mm_plain'")
        conn.commit()
        conn.close()


# --------------------------------------------------------------------------
# Behavior
# --------------------------------------------------------------------------

def test_explicit_year_month_is_respected(client, setup_user, no_op_send, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cr3t")
    res = client.post(
        '/api/trigger-monthly-emails',
        json={"year": 2026, "month": 5},
        headers={"Authorization": "Bearer s3cr3t"},
    )
    assert res.json["year"] == 2026
    assert res.json["month"] == 5
    assert res.json["tally"]["sent"] == 1


def test_default_month_is_previous_calendar_month(client, setup_user, no_op_send, monkeypatch):
    """No year/month in the body -> defaults to utils.dates.get_previous_month_range()."""
    monkeypatch.setenv("CRON_SECRET", "s3cr3t")
    from utils.dates import get_previous_month_range
    expected_start, _ = get_previous_month_range()

    res = client.post(
        '/api/trigger-monthly-emails',
        headers={"Authorization": "Bearer s3cr3t"},
    )
    assert res.status_code == 200
    assert res.json["year"] == expected_start.year
    assert res.json["month"] == expected_start.month


def test_invalid_month_is_rejected(client, setup_user, no_op_send, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cr3t")
    res = client.post(
        '/api/trigger-monthly-emails',
        json={"year": 2026, "month": 13},
        headers={"Authorization": "Bearer s3cr3t"},
    )
    assert res.status_code == 400


def test_running_endpoint_twice_second_time_all_skipped(client, setup_user, no_op_send, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cr3t")
    headers = {"Authorization": "Bearer s3cr3t"}
    first = client.post('/api/trigger-monthly-emails', json={"year": 2026, "month": 5}, headers=headers)
    second = client.post('/api/trigger-monthly-emails', json={"year": 2026, "month": 5}, headers=headers)

    assert first.json["tally"]["sent"] == 1
    assert second.json["tally"]["sent"] == 0
    assert second.json["tally"]["skipped"] == 1


# --------------------------------------------------------------------------
# Settings checkbox
# --------------------------------------------------------------------------

def test_settings_email_form_persists_monthly_opt_in(app, client):
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username = 'settings_u'")
        conn.commit()
    client.post('/register', data={'username': 'settings_u', 'pin': '1234'})
    client.post('/login', data={'username': 'settings_u', 'pin': '1234'})

    res = client.post('/settings/email', data={
        'email': 'settings_u@example.com',
        'email_weekly_summary': '1',
        'email_monthly_summary': '1',
    })
    assert res.status_code in (302, 200)

    with app.app_context():
        conn = get_db()
        row = conn.execute("SELECT email, email_monthly_summary FROM users WHERE username = 'settings_u'").fetchone()

    assert row["email"] == 'settings_u@example.com'
    assert row["email_monthly_summary"] == 1

    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username = 'settings_u'")
        conn.commit()
        conn.close()


def test_settings_email_form_unchecking_monthly_box_opts_out(app, client):
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username = 'settings_u2'")
        conn.commit()
    client.post('/register', data={'username': 'settings_u2', 'pin': '1234'})
    client.post('/login', data={'username': 'settings_u2', 'pin': '1234'})

    # Submit WITHOUT email_monthly_summary in the form -> unchecked checkbox -> opt out (0)
    client.post('/settings/email', data={
        'email': 'settings_u2@example.com',
        'email_weekly_summary': '1',
    })

    with app.app_context():
        conn = get_db()
        row = conn.execute("SELECT email_monthly_summary FROM users WHERE username = 'settings_u2'").fetchone()

    assert row["email_monthly_summary"] == 0

    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username = 'settings_u2'")
        conn.commit()
        conn.close()
