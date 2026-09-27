"""
Tests for services/monthly_summary_delivery.py.

No real network calls: _post_to_resend is monkeypatched at the module
level in every test. RESEND_API_KEY is set per-test since it's required
for a send attempt to even be considered "eligible".
"""

import pytest

from app import app
from db import get_db
import services.monthly_summary_delivery as delivery_mod
from services.monthly_summary_delivery import (
    send_monthly_summary_email,
    send_monthly_summaries_for_all_eligible_users,
    DELIVERY_STATUS_SENT,
    DELIVERY_STATUS_FAILED,
)


@pytest.fixture
def two_users(app, client):
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username IN ('du1', 'du2', 'du3')")
        conn.commit()

        client.post('/register', data={'username': 'du1', 'pin': '1234'})
        client.post('/register', data={'username': 'du2', 'pin': '1234'})
        client.post('/register', data={'username': 'du3', 'pin': '1234'})

        u1 = conn.execute("SELECT id FROM users WHERE username = 'du1'").fetchone()['id']
        u2 = conn.execute("SELECT id FROM users WHERE username = 'du2'").fetchone()['id']
        u3 = conn.execute("SELECT id FROM users WHERE username = 'du3'").fetchone()['id']

        conn.execute("UPDATE users SET email = 'du1@example.com', email_monthly_summary = 1 WHERE id = ?", (u1,))
        conn.execute("UPDATE users SET email = 'du2@example.com', email_monthly_summary = 1 WHERE id = ?", (u2,))
        conn.execute("UPDATE users SET email = NULL WHERE id = ?", (u3,))  # no email
        conn.commit()

        _insert_run(conn, u1, "2026-05-10", 5.0, 25.0, 5.0)
        _insert_run(conn, u2, "2026-05-11", 6.0, 30.0, 5.0)

        yield u1, u2, u3

        conn.execute("DELETE FROM monthly_summary_deliveries WHERE user_id IN (?, ?, ?)", (u1, u2, u3))
        conn.execute("DELETE FROM runs WHERE user_id IN (?, ?, ?)", (u1, u2, u3))
        conn.execute("DELETE FROM users WHERE username IN ('du1', 'du2', 'du3')")
        conn.commit()
        conn.close()


def _insert_run(conn, user_id, date_str, distance_km, time_min, pace):
    conn.execute(
        "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, date_str, distance_km, time_min, pace, round(distance_km * 70, 1)),
    )
    conn.commit()


@pytest.fixture
def with_api_key(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key-123")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "RunRush <noreply@runrush.app>")


def _mock_send(monkeypatch, outcome_by_email=None, default=(True, None)):
    """Replaces _post_to_resend with a fake that never touches the network.
    outcome_by_email maps recipient -> (ok, error); anything not in the map
    uses `default`. Returns the call log (list of recipient emails)."""
    calls = []

    def fake_post(api_key, from_email, to_email, subject, html_body):
        calls.append(to_email)
        if outcome_by_email and to_email in outcome_by_email:
            return outcome_by_email[to_email]
        return default

    monkeypatch.setattr(delivery_mod, "_post_to_resend", fake_post)
    return calls


# --------------------------------------------------------------------------
# Successful send
# --------------------------------------------------------------------------

def test_successful_send_marks_delivery_sent(app, two_users, with_api_key, monkeypatch):
    u1, _, _ = two_users
    calls = _mock_send(monkeypatch)

    with app.app_context():
        result = send_monthly_summary_email(u1, 2026, 5)
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM monthly_summary_deliveries WHERE user_id = ? AND year=2026 AND month=5", (u1,)
        ).fetchone()
        conn.close()

    assert result["status"] == "sent"
    assert calls == ["du1@example.com"]
    assert row["status"] == DELIVERY_STATUS_SENT
    assert row["sent_at"] is not None
    assert row["error"] is None


# --------------------------------------------------------------------------
# Idempotency / duplicate execution protection
# --------------------------------------------------------------------------

def test_duplicate_execution_does_not_send_twice(app, two_users, with_api_key, monkeypatch):
    u1, _, _ = two_users
    calls = _mock_send(monkeypatch)

    with app.app_context():
        first = send_monthly_summary_email(u1, 2026, 5)
        second = send_monthly_summary_email(u1, 2026, 5)

    assert first["status"] == "sent"
    assert second["status"] == "skipped"
    assert second["reason"] == "already_sent"
    assert calls == ["du1@example.com"]  # only ONE real send attempt


def test_force_resend_bypasses_idempotency_guard(app, two_users, with_api_key, monkeypatch):
    u1, _, _ = two_users
    calls = _mock_send(monkeypatch)

    with app.app_context():
        send_monthly_summary_email(u1, 2026, 5)
        result = send_monthly_summary_email(u1, 2026, 5, force=True)

    assert result["status"] == "sent"
    assert calls == ["du1@example.com", "du1@example.com"]


def test_batch_run_twice_only_counts_one_sent_per_user(app, two_users, with_api_key, monkeypatch):
    u1, u2, u3 = two_users
    calls = _mock_send(monkeypatch)

    with app.app_context():
        first_batch = send_monthly_summaries_for_all_eligible_users(2026, 5)
        second_batch = send_monthly_summaries_for_all_eligible_users(2026, 5)

    assert first_batch["tally"]["sent"] == 2   # u1, u2 (u3 has no email)
    assert second_batch["tally"]["sent"] == 0
    assert second_batch["tally"]["skipped"] == 2
    assert calls.count("du1@example.com") == 1
    assert calls.count("du2@example.com") == 1


# --------------------------------------------------------------------------
# Failure handling
# --------------------------------------------------------------------------

def test_send_failure_marks_delivery_failed_with_error(app, two_users, with_api_key, monkeypatch):
    u1, _, _ = two_users
    _mock_send(monkeypatch, outcome_by_email={"du1@example.com": (False, "HTTPError 500: boom")})

    with app.app_context():
        result = send_monthly_summary_email(u1, 2026, 5)
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM monthly_summary_deliveries WHERE user_id = ? AND year=2026 AND month=5", (u1,)
        ).fetchone()
        conn.close()

    assert result["status"] == "failed"
    assert result["reason"] == "HTTPError 500: boom"
    assert row["status"] == DELIVERY_STATUS_FAILED
    assert row["error"] == "HTTPError 500: boom"
    assert row["sent_at"] is None


def test_retry_after_failure_can_succeed_and_flips_status_to_sent(app, two_users, with_api_key, monkeypatch):
    u1, _, _ = two_users

    with app.app_context():
        _mock_send(monkeypatch, default=(False, "temporary outage"))
        first = send_monthly_summary_email(u1, 2026, 5)
        assert first["status"] == "failed"

        # Retry (force=True, simulating an operator re-running after a fix) succeeds
        _mock_send(monkeypatch, default=(True, None))
        second = send_monthly_summary_email(u1, 2026, 5, force=True)

        conn = get_db()
        row = conn.execute(
            "SELECT * FROM monthly_summary_deliveries WHERE user_id = ? AND year=2026 AND month=5", (u1,)
        ).fetchone()
        conn.close()

    assert second["status"] == "sent"
    assert row["status"] == DELIVERY_STATUS_SENT


def test_one_user_failure_does_not_block_the_rest_of_the_batch(app, two_users, with_api_key, monkeypatch):
    u1, u2, u3 = two_users
    calls = _mock_send(monkeypatch, outcome_by_email={"du1@example.com": (False, "boom")})

    with app.app_context():
        result = send_monthly_summaries_for_all_eligible_users(2026, 5)

    assert result["tally"]["failed"] == 1
    assert result["tally"]["sent"] == 1
    assert set(calls) == {"du1@example.com", "du2@example.com"}


# --------------------------------------------------------------------------
# Ineligibility (never recorded as a delivery attempt)
# --------------------------------------------------------------------------

def test_user_with_no_email_is_ineligible_and_not_sent(app, two_users, with_api_key, monkeypatch):
    _, _, u3 = two_users
    calls = _mock_send(monkeypatch)

    with app.app_context():
        result = send_monthly_summary_email(u3, 2026, 5)
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM monthly_summary_deliveries WHERE user_id = ? AND year=2026 AND month=5", (u3,)
        ).fetchone()
        conn.close()

    assert result["status"] == "ineligible"
    assert result["reason"] == "no_email_or_opted_out"
    assert calls == []
    assert row is None  # no delivery row for something that was never attempted


def test_opted_out_user_is_ineligible(app, two_users, with_api_key, monkeypatch):
    u1, _, _ = two_users
    calls = _mock_send(monkeypatch)

    with app.app_context():
        conn = get_db()
        conn.execute("UPDATE users SET email_monthly_summary = 0 WHERE id = ?", (u1,))
        conn.commit()

        result = send_monthly_summary_email(u1, 2026, 5)

    assert result["status"] == "ineligible"
    assert calls == []


def test_missing_api_key_is_ineligible_and_never_calls_resend(app, two_users, monkeypatch):
    u1, _, _ = two_users
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    calls = _mock_send(monkeypatch)

    with app.app_context():
        result = send_monthly_summary_email(u1, 2026, 5)

    assert result["status"] == "ineligible"
    assert result["reason"] == "no_api_key_configured"
    assert calls == []


# --------------------------------------------------------------------------
# User isolation in batch sends
# --------------------------------------------------------------------------

def test_batch_only_targets_eligible_users_excludes_no_email(app, two_users, with_api_key, monkeypatch):
    u1, u2, u3 = two_users
    calls = _mock_send(monkeypatch)

    with app.app_context():
        result = send_monthly_summaries_for_all_eligible_users(2026, 5)

    assert u3 not in [d["user_id"] for d in result["details"]]
    assert "du1@example.com" in calls and "du2@example.com" in calls
    assert len(calls) == 2
