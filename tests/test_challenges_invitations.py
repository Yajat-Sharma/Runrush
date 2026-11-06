"""
Tests for RunRush Friendly Challenges Phase 3: Invitation Workflow & Endpoints.
Covers:
- Wrong-user acceptance
- Wrong-user rejection
- Repeated acceptance
- Repeated rejection
- Expired invitation acceptance & rejection
- Multiple invitations query
- Cross-user isolation on details and actions
- Cancellation by challenger vs opponent
- Status transition to SCHEDULED vs ACTIVE
"""

from datetime import datetime, timedelta, timezone
import pytest
from app import app
from db import get_db
from services.friendly_challenge_service import (
    create_friendly_challenge_tables,
    create_challenge,
    get_challenge_display_status,
)


@pytest.fixture(autouse=True)
def setup_challenge_db(app):
    """Ensure in-memory SQLite tables exist."""
    conn = get_db()
    create_friendly_challenge_tables(conn)
    conn.commit()
    conn.close()


def create_test_user(client, username, email, display_name):
    """Helper to insert user directly into test DB."""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO users (username, pin, display_name, profile_emoji, status) "
        "VALUES (?, 'dummy_pin', ?, '🏃', 'active')",
        (username, display_name)
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    return user_id


def test_invitations_requires_authentication(client):
    res = client.get("/api/challenges/invitations")
    assert res.status_code == 401


def test_list_multiple_invitations(client):
    u1 = create_test_user(client, "challenger1", "c1@test.com", "Challenger One")
    u2 = create_test_user(client, "challenger2", "c2@test.com", "Challenger Two")
    target = create_test_user(client, "target_runner", "t@test.com", "Target Runner")

    today = datetime.now(timezone.utc).date()
    start_str = str(today)
    end_str = str(today + timedelta(days=7))

    conn = get_db()
    c1 = create_challenge(u1, target, "DISTANCE", start_str, end_str, tz_name="UTC", title="Duel 1", message="Let's go!", conn=conn)
    c2 = create_challenge(u2, target, "LONGEST", start_str, end_str, tz_name="UTC", title="Duel 2", conn=conn)
    conn.close()

    # Log in as target runner
    with client.session_transaction() as sess:
        sess["user_id"] = target

    res = client.get("/api/challenges/invitations")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert len(data["incoming"]) == 2
    assert data["pending_count"] == 2

    # Check challenger info is populated
    challengers = [inv["challenger"]["username"] for inv in data["incoming"]]
    assert "challenger1" in challengers
    assert "challenger2" in challengers


def test_wrong_user_cannot_accept_invitation(client):
    u1 = create_test_user(client, "alice", "alice@test.com", "Alice")
    u2 = create_test_user(client, "bob", "bob@test.com", "Bob")
    u3 = create_test_user(client, "charlie", "charlie@test.com", "Charlie")

    today = datetime.now(timezone.utc).date()
    conn = get_db()
    chal_id = create_challenge(u1, u2, "DISTANCE", str(today), str(today + timedelta(days=7)), tz_name="UTC", conn=conn)
    conn.close()

    # Charlie attempts to accept Alice's challenge to Bob
    with client.session_transaction() as sess:
        sess["user_id"] = u3

    res = client.post(f"/api/challenges/{chal_id}/accept")
    assert res.status_code == 403
    assert "opponent" in res.get_json()["error"].lower()

    # Alice (challenger) also cannot accept her own challenge
    with client.session_transaction() as sess:
        sess["user_id"] = u1
    res = client.post(f"/api/challenges/{chal_id}/accept")
    assert res.status_code == 403


def test_wrong_user_cannot_reject_invitation(client):
    u1 = create_test_user(client, "alice_rej", "a_rej@test.com", "Alice")
    u2 = create_test_user(client, "bob_rej", "b_rej@test.com", "Bob")
    u3 = create_test_user(client, "eve_rej", "eve@test.com", "Eve")

    today = datetime.now(timezone.utc).date()
    conn = get_db()
    chal_id = create_challenge(u1, u2, "DISTANCE", str(today), str(today + timedelta(days=7)), tz_name="UTC", conn=conn)
    conn.close()

    with client.session_transaction() as sess:
        sess["user_id"] = u3

    res = client.post(f"/api/challenges/{chal_id}/reject")
    assert res.status_code == 403


def test_successful_acceptance_transitions_to_active_or_scheduled(client):
    u1 = create_test_user(client, "runner_a", "ra@test.com", "Runner A")
    u2 = create_test_user(client, "runner_b", "rb@test.com", "Runner B")

    today = datetime.now(timezone.utc).date()
    # Active right now because start_date is today
    conn = get_db()
    chal_active = create_challenge(u1, u2, "DISTANCE", str(today), str(today + timedelta(days=7)), tz_name="UTC", conn=conn)

    # Future scheduled challenge
    future_start = today + timedelta(days=5)
    future_end = today + timedelta(days=12)
    chal_scheduled = create_challenge(u1, u2, "DAILY", str(future_start), str(future_start), tz_name="UTC", conn=conn)
    conn.close()

    with client.session_transaction() as sess:
        sess["user_id"] = u2

    # Accept active challenge
    res1 = client.post(f"/api/challenges/{chal_active}/accept")
    assert res1.status_code == 200
    data1 = res1.get_json()
    assert data1["status"] == "success"
    assert data1["display_status"] == "ACTIVE"

    # Accept scheduled challenge
    res2 = client.post(f"/api/challenges/{chal_scheduled}/accept")
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert data2["status"] == "success"
    assert data2["display_status"] == "SCHEDULED"

    # Verify notifications were created for challenger u1
    conn = get_db()
    notifs = conn.execute(
        "SELECT n.title, n.message FROM notifications n "
        "JOIN user_notifications un ON n.id = un.notification_id "
        "WHERE un.user_id = ? AND n.type = 'CHALLENGE_ACCEPTED'",
        (u1,)
    ).fetchall()
    conn.close()
    assert len(notifs) >= 2


def test_repeated_acceptance_fails(client):
    u1 = create_test_user(client, "rep_a", "rep_a@test.com", "Rep A")
    u2 = create_test_user(client, "rep_b", "rep_b@test.com", "Rep B")

    today = datetime.now(timezone.utc).date()
    conn = get_db()
    chal_id = create_challenge(u1, u2, "DISTANCE", str(today), str(today + timedelta(days=7)), tz_name="UTC", conn=conn)
    conn.close()

    with client.session_transaction() as sess:
        sess["user_id"] = u2

    res1 = client.post(f"/api/challenges/{chal_id}/accept")
    assert res1.status_code == 200

    # Second accept attempt
    res2 = client.post(f"/api/challenges/{chal_id}/accept")
    assert res2.status_code == 400
    assert "status" in res2.get_json()["error"].lower()


def test_repeated_rejection_fails(client):
    u1 = create_test_user(client, "rr_a", "rr_a@test.com", "RR A")
    u2 = create_test_user(client, "rr_b", "rr_b@test.com", "RR B")

    today = datetime.now(timezone.utc).date()
    conn = get_db()
    chal_id = create_challenge(u1, u2, "DISTANCE", str(today), str(today + timedelta(days=7)), tz_name="UTC", conn=conn)
    conn.close()

    with client.session_transaction() as sess:
        sess["user_id"] = u2

    res1 = client.post(f"/api/challenges/{chal_id}/reject")
    assert res1.status_code == 200
    assert res1.get_json()["status"] == "success"

    # Second reject attempt
    res2 = client.post(f"/api/challenges/{chal_id}/reject")
    assert res2.status_code == 400


def test_cannot_accept_expired_invitation(client):
    u1 = create_test_user(client, "exp_a", "exp_a@test.com", "Exp A")
    u2 = create_test_user(client, "exp_b", "exp_b@test.com", "Exp B")

    # Past dates (e.g., 20 days ago)
    past_start = (datetime.now(timezone.utc) - timedelta(days=20)).strftime("%Y-%m-%d")
    past_end = (datetime.now(timezone.utc) - timedelta(days=13)).strftime("%Y-%m-%d")

    conn = get_db()
    # Insert directly with past end_date
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("""
        INSERT INTO friendly_challenges (
            challenger_id, opponent_id, challenge_type, start_date, end_date,
            challenge_timezone, status, created_at, updated_at
        ) VALUES (?, ?, 'DISTANCE', ?, ?, 'UTC', 'INVITED', ?, ?)
    """, (u1, u2, past_start, past_end, now_str, now_str))
    chal_id = cur.lastrowid
    conn.commit()
    conn.close()

    with client.session_transaction() as sess:
        sess["user_id"] = u2

    # Attempt to accept
    res = client.post(f"/api/challenges/{chal_id}/accept")
    assert res.status_code == 400
    assert "expired" in res.get_json()["error"].lower()

    # Verify status transitioned to EXPIRED in database
    conn = get_db()
    row = conn.execute("SELECT status FROM friendly_challenges WHERE id = ?", (chal_id,)).fetchone()
    conn.close()
    assert row["status"] == "EXPIRED"


def test_challenger_can_cancel_invitation(client):
    u1 = create_test_user(client, "cancel_a", "cancel_a@test.com", "Cancel A")
    u2 = create_test_user(client, "cancel_b", "cancel_b@test.com", "Cancel B")

    today = datetime.now(timezone.utc).date()
    conn = get_db()
    chal_id = create_challenge(u1, u2, "DISTANCE", str(today), str(today + timedelta(days=7)), tz_name="UTC", conn=conn)
    conn.close()

    # Opponent cannot cancel
    with client.session_transaction() as sess:
        sess["user_id"] = u2
    res_opp = client.post(f"/api/challenges/{chal_id}/cancel")
    assert res_opp.status_code == 403

    # Challenger can cancel
    with client.session_transaction() as sess:
        sess["user_id"] = u1
    res_chal = client.post(f"/api/challenges/{chal_id}/cancel")
    assert res_chal.status_code == 200
    assert res_chal.get_json()["status"] == "success"

    # Status is now CANCELLED
    conn = get_db()
    row = conn.execute("SELECT status FROM friendly_challenges WHERE id = ?", (chal_id,)).fetchone()
    conn.close()
    assert row["status"] == "CANCELLED"


def test_cross_user_isolation_on_challenge_details(client):
    u1 = create_test_user(client, "priv_a", "pa@test.com", "Priv A")
    u2 = create_test_user(client, "priv_b", "pb@test.com", "Priv B")
    u3 = create_test_user(client, "priv_c", "pc@test.com", "Priv C")

    today = datetime.now(timezone.utc).date()
    conn = get_db()
    chal_id = create_challenge(u1, u2, "DISTANCE", str(today), str(today + timedelta(days=7)), tz_name="UTC", conn=conn)
    conn.close()

    # Participant A can view
    with client.session_transaction() as sess:
        sess["user_id"] = u1
    res1 = client.get(f"/api/challenges/{chal_id}")
    assert res1.status_code == 200
    assert res1.get_json()["status"] == "success"

    # Participant B can view
    with client.session_transaction() as sess:
        sess["user_id"] = u2
    res2 = client.get(f"/api/challenges/{chal_id}")
    assert res2.status_code == 200

    # Non-participant C cannot view details
    with client.session_transaction() as sess:
        sess["user_id"] = u3
    res3 = client.get(f"/api/challenges/{chal_id}")
    assert res3.status_code == 403
    assert "participant" in res3.get_json()["error"].lower()
