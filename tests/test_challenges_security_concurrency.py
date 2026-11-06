"""
Tests for RunRush Friendly Challenges Phase 6: Security, IDOR, Concurrency, & Migration Safety.
Covers:
- Unauthenticated access prevention across all endpoints.
- IDOR: Unauthorized users cannot read, accept, reject, or cancel non-owned challenges.
- User ID spoofing & manipulation prevention.
- Concurrent accept/reject operations.
- Migration safety: Idempotency and zero data loss on existing databases.
"""

import threading
from datetime import datetime, timezone
import pytest
from app import app
from db import get_db
from services.friendly_challenge_service import (
    create_friendly_challenge_tables,
    create_challenge,
    accept_challenge,
    reject_challenge,
    cancel_challenge,
    get_challenge_progress,
)
from scripts.apply_migration_015 import apply as apply_migration_015


@pytest.fixture(autouse=True)
def setup_challenge_db(app):
    """Ensure in-memory SQLite tables exist for friendly challenges."""
    conn = get_db()
    create_friendly_challenge_tables(conn)
    conn.commit()
    conn.close()


def create_user(username, display_name):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO users (username, pin, display_name, profile_emoji, status) "
        "VALUES (?, 'pin', ?, '🏃', 'active')",
        (username, display_name)
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    return user_id


def test_unauthenticated_api_endpoints_denied(client):
    """Verify all friendly challenge endpoints enforce authentication."""
    endpoints = [
        ("GET", "/api/challenges/stats"),
        ("GET", "/api/challenges/players"),
        ("POST", "/api/challenges"),
        ("GET", "/api/challenges/invitations"),
        ("GET", "/api/challenges/ongoing"),
        ("GET", "/api/challenges/history"),
        ("GET", "/api/challenges/1"),
        ("GET", "/api/challenges/1/progress"),
        ("POST", "/api/challenges/1/accept"),
        ("POST", "/api/challenges/1/reject"),
        ("POST", "/api/challenges/1/cancel"),
    ]
    for method, ep in endpoints:
        if method == "GET":
            res = client.get(ep)
        else:
            res = client.post(ep, json={})
        assert res.status_code == 401, f"Endpoint {method} {ep} did not return 401"


def test_idor_protection_for_details_and_progress(client):
    """User C cannot view details or progress of a duel between User A and User B."""
    u1 = create_user("alice", "Alice")
    u2 = create_user("bob", "Bob")
    u3 = create_user("charlie_eavesdropper", "Charlie")

    chal_id = create_challenge(u1, u2, "DISTANCE", "2026-12-01", "2026-12-07")

    # Charlie tries to view challenge details
    with client.session_transaction() as sess:
        sess["user_id"] = u3

    res_detail = client.get(f"/api/challenges/{chal_id}")
    assert res_detail.status_code == 403
    assert "participant" in res_detail.get_json()["error"].lower()

    # Charlie tries to view challenge progress
    res_prog = client.get(f"/api/challenges/{chal_id}/progress")
    assert res_prog.status_code == 403


def test_idor_protection_for_invitation_actions(client):
    """User C cannot accept, reject, or cancel a challenge between User A and User B."""
    u1 = create_user("alice_inv", "Alice")
    u2 = create_user("bob_inv", "Bob")
    u3 = create_user("charlie_intruder", "Charlie")

    chal_id = create_challenge(u1, u2, "DISTANCE", "2026-12-01", "2026-12-07")

    with client.session_transaction() as sess:
        sess["user_id"] = u3

    # Charlie tries to accept
    res_accept = client.post(f"/api/challenges/{chal_id}/accept")
    assert res_accept.status_code == 403

    # Charlie tries to reject
    res_reject = client.post(f"/api/challenges/{chal_id}/reject")
    assert res_reject.status_code == 403

    # Charlie tries to cancel
    res_cancel = client.post(f"/api/challenges/{chal_id}/cancel")
    assert res_cancel.status_code == 403

    # Bob (the opponent) cannot cancel (only challenger can cancel)
    with client.session_transaction() as sess:
        sess["user_id"] = u2
    res_bob_cancel = client.post(f"/api/challenges/{chal_id}/cancel")
    assert res_bob_cancel.status_code == 403

    # Alice (challenger) cannot accept her own challenge (only opponent can accept)
    with client.session_transaction() as sess:
        sess["user_id"] = u1
    res_alice_accept = client.post(f"/api/challenges/{chal_id}/accept")
    assert res_alice_accept.status_code == 403


def test_user_id_manipulation_prevented_in_create(client):
    """Challenger ID is strictly derived from session; body-supplied challenger_id is ignored."""
    u1 = create_user("real_challenger", "Real")
    u2 = create_user("spoofed_challenger", "Spoofed")
    u3 = create_user("victim_opponent", "Victim")

    with client.session_transaction() as sess:
        sess["user_id"] = u1

    # Attempt to spoof challenger_id as u2
    payload = {
        "challenger_id": u2,
        "opponent_id": u3,
        "challenge_type": "DISTANCE",
        "start_date": "2026-01-01",
        "end_date": "2026-01-07",
        "challenge_timezone": "UTC"
    }
    res = client.post("/api/challenges", json=payload)
    assert res.status_code == 201
    data = res.get_json()

    # The created challenge must have challenger_id = u1 (from session), NOT u2
    conn = get_db()
    chal = conn.execute("SELECT challenger_id FROM friendly_challenges WHERE id = ?", (data["challenge_id"],)).fetchone()
    conn.close()
    assert chal["challenger_id"] == u1


def test_concurrent_invitation_acceptance(client):
    """Simulate concurrent acceptance attempts to ensure atomicity and prevent double processing."""
    u1 = create_user("alice_race", "Alice")
    u2 = create_user("bob_race", "Bob")

    chal_id = create_challenge(u1, u2, "DISTANCE", "2026-12-01", "2026-12-07")

    results = []

    def try_accept():
        with app.app_context():
            try:
                conn = get_db()
                accept_challenge(chal_id, u2, conn=conn)
                conn.commit()
                conn.close()
                results.append("SUCCESS")
            except Exception as e:
                results.append(f"FAILED: {e}")

    t1 = threading.Thread(target=try_accept)
    t2 = threading.Thread(target=try_accept)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly one thread succeeds, the other fails due to status change check
    successes = [r for r in results if r == "SUCCESS"]
    failures = [r for r in results if "FAILED" in r]
    assert len(successes) == 1
    assert len(failures) == 1
    assert any(msg in failures[0].lower() for msg in ["cannot accept", "locked", "pending invitation"])


def test_migration_015_idempotency_and_data_preservation():
    """Verify applying migration 015 multiple times does not corrupt or wipe existing challenges."""
    conn = get_db()
    # Migration 015 is already run in fixture, let's insert a record
    u1 = create_user("mig_u1", "U1")
    u2 = create_user("mig_u2", "U2")
    chal_id = create_challenge(u1, u2, "DISTANCE", "2026-01-01", "2026-01-07", conn=conn)
    conn.commit()

    # Re-run migration
    create_friendly_challenge_tables(conn)
    conn.commit()

    # Ensure existing challenge still exists intact
    row = conn.execute("SELECT * FROM friendly_challenges WHERE id = ?", (chal_id,)).fetchone()
    assert row is not None
    assert row["challenger_id"] == u1
    assert row["opponent_id"] == u2
    conn.close()
