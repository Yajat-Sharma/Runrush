"""
Tests for services/monthly_summary_delivery.py.

No real network calls: _post_to_resend is monkeypatched at the module
level in every test. RESEND_API_KEY is set per-test since it's required
for a send attempt to even be considered "eligible".
"""

import threading

import pytest

from app import app
from db import get_db
import services.monthly_summary_delivery as delivery_mod
from services.monthly_summary_delivery import (
    send_monthly_summary_email,
    send_monthly_summaries_for_all_eligible_users,
    _claim_delivery,
    DELIVERY_STATUS_PENDING,
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


# ==========================================================================
# Production-safety audit fixes: FIX 1 (failure isolation) and
# FIX 2 (atomic delivery claim / concurrency)
# ==========================================================================

# --------------------------------------------------------------------------
# FIX 2 — atomic claim behavior, tested directly
# --------------------------------------------------------------------------

def test_first_claim_succeeds_on_fresh_delivery(app, two_users):
    u1, _, _ = two_users
    with app.app_context():
        conn = get_db()
        delivery_id = _claim_delivery(conn, u1, 2026, 5)
        row = conn.execute(
            "SELECT * FROM monthly_summary_deliveries WHERE user_id = ? AND year=2026 AND month=5", (u1,)
        ).fetchone()

    assert delivery_id is not None
    assert row["status"] == DELIVERY_STATUS_PENDING


def test_second_claim_cannot_claim_while_first_is_pending(app, two_users):
    """Direct proof of the atomic-claim property: back-to-back calls with
    no send happening in between (the first claim is left at PENDING,
    exactly the state it would be in mid-send in a real race) — the second
    claim must be refused."""
    u1, _, _ = two_users
    with app.app_context():
        conn = get_db()
        first_id = _claim_delivery(conn, u1, 2026, 5)
        second_id = _claim_delivery(conn, u1, 2026, 5)

    assert first_id is not None
    assert second_id is None


def test_losing_claim_never_calls_resend(app, two_users, with_api_key, monkeypatch):
    """The higher-level guarantee that matters: a caller that could not
    claim the slot must never reach _post_to_resend at all."""
    u1, _, _ = two_users
    with app.app_context():
        conn = get_db()
        _claim_delivery(conn, u1, 2026, 5)  # simulate another request already holding PENDING
        conn.close()

    calls = _mock_send(monkeypatch)
    with app.app_context():
        result = send_monthly_summary_email(u1, 2026, 5)

    assert result["status"] == "skipped"
    assert result["reason"] == "claim_in_progress"
    assert calls == []


def test_true_concurrent_claim_attempt_only_one_winner(app, two_users):
    """
    Best-effort TRUE concurrency test: two real OS threads, each pushing
    its own Flask app context (so each gets its own g.db / DB connection,
    not a shared one), racing to claim the same (user_id, year, month) via
    a threading.Barrier to maximize overlap.

    Limitation (documented, not swept under the rug): SQLite's global
    interpreter-level contention and file locking mean this doesn't prove
    true multi-process safety the way it would against a real Postgres
    server under this test infrastructure — a second writer racing tightly
    enough can hit sqlite3.OperationalError('database is locked') instead
    of cleanly losing the ON CONFLICT WHERE check, which _claim_delivery
    treats identically (returns None either way — see its docstring). What
    this test DOES prove: under real thread-level concurrency against the
    actual shared test database, at most one of the two racing claims ever
    succeeds — never both. The atomic-claim SQL itself (proven separately
    in test_second_claim_cannot_claim_while_first_is_pending) is what
    carries the correctness guarantee for the real Postgres production
    path, where ON CONFLICT is natively safe across separate processes.
    """
    u1, _, _ = two_users
    results = []
    barrier = threading.Barrier(2)

    def attempt():
        with app.app_context():
            conn = get_db()
            try:
                barrier.wait(timeout=5)
            except threading.BrokenBarrierError:
                pass
            claimed_id = _claim_delivery(conn, u1, 2026, 5)
            results.append(claimed_id)

    t1 = threading.Thread(target=attempt)
    t2 = threading.Thread(target=attempt)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert len(results) == 2
    non_none = [r for r in results if r is not None]
    # Exactly one winner — never both, regardless of which one it was.
    assert len(non_none) == 1, f"expected exactly one successful claim, got {results}"


def test_failed_delivery_is_retryable_via_claim(app, two_users):
    u1, _, _ = two_users
    with app.app_context():
        conn = get_db()
        delivery_id = _claim_delivery(conn, u1, 2026, 5)
        delivery_mod._finalize_delivery(conn, delivery_id, DELIVERY_STATUS_FAILED, error="boom", sent_at=None)

        retry_id = _claim_delivery(conn, u1, 2026, 5)

    assert retry_id is not None  # FAILED must be retryable


def test_sent_delivery_is_not_reclaimable_without_force(app, two_users):
    u1, _, _ = two_users
    with app.app_context():
        conn = get_db()
        delivery_id = _claim_delivery(conn, u1, 2026, 5)
        delivery_mod._finalize_delivery(conn, delivery_id, DELIVERY_STATUS_SENT, error=None, sent_at="2026-05-31 12:00:00")

        reclaim_id = _claim_delivery(conn, u1, 2026, 5)
        forced_reclaim_id = _claim_delivery(conn, u1, 2026, 5, force=True)

    assert reclaim_id is None
    assert forced_reclaim_id is not None


# --------------------------------------------------------------------------
# FIX 2 — unexpected exception during send transitions PENDING -> FAILED
# --------------------------------------------------------------------------

def test_unexpected_exception_during_send_transitions_pending_to_failed(app, two_users, with_api_key, monkeypatch):
    """Not a controlled (False, error) return from _post_to_resend — an
    actually-raised exception, e.g. a bug in rendering or a network layer
    throwing instead of returning. The claimed PENDING row must still be
    resolved to FAILED, not left stuck."""
    u1, _, _ = two_users

    def boom(*a, **kw):
        raise RuntimeError("unexpected network stack failure")

    monkeypatch.setattr(delivery_mod, "_post_to_resend", boom)

    with app.app_context():
        result = send_monthly_summary_email(u1, 2026, 5)
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM monthly_summary_deliveries WHERE user_id = ? AND year=2026 AND month=5", (u1,)
        ).fetchone()

    assert result["status"] == "failed"
    assert "RuntimeError" in result["reason"]
    assert row["status"] == DELIVERY_STATUS_FAILED
    assert row["status"] != DELIVERY_STATUS_PENDING  # never left stuck


# --------------------------------------------------------------------------
# FIX 1 — batch survives an unexpected exception, not just an expected False
# --------------------------------------------------------------------------

def test_batch_continues_after_one_user_raises_unexpected_exception(app, two_users, with_api_key, monkeypatch):
    """This is the regression test the audit specifically asked for:
    one user's send_monthly_summary_email call RAISES (not just returns a
    failure dict) — later users must still be processed and succeed."""
    u1, u2, u3 = two_users
    calls = []

    original_post = delivery_mod._post_to_resend

    def flaky_post(api_key, from_email, to_email, subject, html_body):
        calls.append(to_email)
        if to_email == "du1@example.com":
            raise RuntimeError("simulated unexpected crash for user A")
        return True, None

    monkeypatch.setattr(delivery_mod, "_post_to_resend", flaky_post)

    with app.app_context():
        result = send_monthly_summaries_for_all_eligible_users(2026, 5)

    assert result["tally"]["failed"] == 1
    assert result["tally"]["sent"] == 1
    # Both eligible users (u1, u2) were attempted — u3 has no email, excluded.
    assert set(calls) == {"du1@example.com", "du2@example.com"}
    # The batch call itself did not raise/crash the whole process.
    detail_for_u1 = next(d for d in result["details"] if d["user_id"] == u1)
    assert detail_for_u1["status"] == "failed"
    assert "RuntimeError" in detail_for_u1["reason"]
