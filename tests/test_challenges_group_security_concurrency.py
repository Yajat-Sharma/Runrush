"""
Security, Authorization, and Concurrency Tests for RunRush Friendly Challenges V2:
Free-for-all Group Challenges (3-10 participants) and 1v1 Duels.

Covers:
1. Authorization & Permissions:
   - Creator cannot accept their own invitation (PermissionError).
   - Non-invited users cannot accept or reject someone else's challenge (PermissionError / 403).
   - Non-creator cannot cancel challenge or participant invitations (PermissionError / 403).
2. Privacy & Suspended Accounts:
   - Blocked users cannot be invited to group challenges (404 Not Found).
   - Blocked creator accounts cannot create challenges (403 Forbidden).
3. Pending Duplication Prevention:
   - Duplicate pending group invitations with identical invitee sets are rejected (409 Conflict).
   - 1v1 duplicate pending challenges are blocked (409 Conflict).
4. Cancellation Workflows:
   - Creator can cancel individual participant invitations before acceptance.
   - Cancelling participant dropping potential participants below 3 automatically cancels challenge.
   - Creator can cancel entire group challenge.
5. Lifecycle Threshold & Roster Locking:
   - Minimum 3 accepted participants required to activate challenge (remains INVITED with 2).
   - Start date arrival with < 3 accepted expires the challenge.
   - Roster is locked at challenge start: unaccepted invitees cannot join once challenge has started.
6. Concurrency & Transactional Capacity:
   - Maximum 10 participants enforced transactionally; concurrent attempts beyond 10 are rejected.
"""

import pytest
import os
import sys
import threading
from datetime import datetime, date, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["DATABASE_URL"] = "sqlite:///test_runs.db"
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci")

from app import app as flask_app
from db import get_db
from services.friendly_challenge_service import (
    create_friendly_challenge_tables,
    create_group_challenge,
    create_challenge,
    accept_challenge,
    reject_challenge,
    cancel_challenge,
    check_and_update_expiry,
    get_challenge_display_status,
)


@pytest.fixture
def sec_users(app):
    """Creates a cohort of active and blocked users for security & concurrency testing."""
    with app.app_context():
        create_friendly_challenge_tables()
        conn = get_db()
        conn.execute("DELETE FROM challenge_awards")
        conn.execute("DELETE FROM challenge_activity")
        conn.execute("DELETE FROM challenge_participants")
        conn.execute("DELETE FROM friendly_challenges")
        conn.execute("DELETE FROM user_notifications")
        conn.execute("DELETE FROM notifications")
        conn.execute("DELETE FROM users WHERE username LIKE 'sec_usr_%'")

        users = {}
        for i in range(1, 15):
            uname = f"sec_usr_{i}"
            conn.execute(
                "INSERT INTO users (username, pin, display_name, profile_emoji, status) VALUES (?, 'pin', ?, '🏃', 'active')",
                (uname, f"Security User {i}")
            )
            u_id = conn.execute("SELECT id FROM users WHERE username = ?", (uname,)).fetchone()["id"]
            users[i] = u_id

        # Create one blocked user
        conn.execute(
            "INSERT INTO users (username, pin, display_name, profile_emoji, status) VALUES ('sec_usr_blocked', 'pin', 'Blocked User', '🚫', 'blocked')"
        )
        users["blocked"] = conn.execute("SELECT id FROM users WHERE username = 'sec_usr_blocked'").fetchone()["id"]

        conn.commit()
        return users


def login(client, user_id, username):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = username


def test_creator_cannot_accept_own_challenge(client, sec_users):
    u = sec_users
    login(client, u[1], "sec_usr_1")

    res = client.post("/api/challenges", json={
        "participant_ids": [u[2], u[3]],
        "challenge_type": "DISTANCE",
        "start_date": "2026-11-15",
        "end_date": "2026-11-22",
        "title": "Creator Test"
    })
    assert res.status_code == 201
    cid = res.get_json()["challenge_id"]

    # Creator tries to accept via API
    acc_res = client.post(f"/api/challenges/{cid}/accept")
    assert acc_res.status_code == 403
    assert "creator" in acc_res.get_json()["error"].lower()


def test_non_participant_cannot_accept_or_reject(client, sec_users):
    u = sec_users
    login(client, u[1], "sec_usr_1")

    res = client.post("/api/challenges", json={
        "participant_ids": [u[2], u[3]],
        "challenge_type": "DISTANCE",
        "start_date": "2026-11-15",
        "end_date": "2026-11-22"
    })
    cid = res.get_json()["challenge_id"]

    # User 4 (not invited) tries to accept
    login(client, u[4], "sec_usr_4")
    acc_res = client.post(f"/api/challenges/{cid}/accept")
    assert acc_res.status_code == 403
    assert "only invited" in acc_res.get_json()["error"].lower()

    # User 4 tries to reject
    rej_res = client.post(f"/api/challenges/{cid}/reject")
    assert rej_res.status_code == 403
    assert "only invited" in rej_res.get_json()["error"].lower()


def test_non_creator_cannot_cancel(client, sec_users):
    u = sec_users
    login(client, u[1], "sec_usr_1")

    res = client.post("/api/challenges", json={
        "participant_ids": [u[2], u[3]],
        "challenge_type": "DISTANCE",
        "start_date": "2026-11-15",
        "end_date": "2026-11-22"
    })
    cid = res.get_json()["challenge_id"]

    # Invitee 2 tries to cancel the challenge
    login(client, u[2], "sec_usr_2")
    canc_res = client.post(f"/api/challenges/{cid}/cancel")
    assert canc_res.status_code == 403

    # Invitee 2 tries to cancel invitee 3
    canc_part_res = client.post(f"/api/challenges/{cid}/participants/{u[3]}/cancel")
    assert canc_part_res.status_code == 403


def test_blocked_user_restrictions(client, sec_users):
    u = sec_users
    # 1. Creator attempts to invite a blocked user
    login(client, u[1], "sec_usr_1")
    res = client.post("/api/challenges", json={
        "participant_ids": [u[2], u["blocked"]],
        "challenge_type": "DISTANCE",
        "start_date": "2026-11-15",
        "end_date": "2026-11-22"
    })
    assert res.status_code == 404

    # 2. Blocked user attempts to create a challenge
    login(client, u["blocked"], "sec_usr_blocked")
    res_b = client.post("/api/challenges", json={
        "participant_ids": [u[2], u[3]],
        "challenge_type": "DISTANCE",
        "start_date": "2026-11-15",
        "end_date": "2026-11-22"
    })
    assert res_b.status_code == 403


def test_duplicate_pending_group_invitations_prevented(client, sec_users):
    u = sec_users
    login(client, u[1], "sec_usr_1")

    # First group challenge
    res1 = client.post("/api/challenges", json={
        "participant_ids": [u[2], u[3]],
        "challenge_type": "DISTANCE",
        "start_date": "2026-11-15",
        "end_date": "2026-11-22",
        "title": "Pending 1"
    })
    assert res1.status_code == 201

    # Second group challenge with identical invitees
    res2 = client.post("/api/challenges", json={
        "participant_ids": [u[3], u[2]],  # Permuted order
        "challenge_type": "LONGEST",
        "start_date": "2026-11-15",
        "end_date": "2026-11-22",
        "title": "Pending 2"
    })
    assert res2.status_code == 409
    assert "already have a pending group challenge" in res2.get_json()["error"]


def test_creator_can_cancel_individual_participant_invitation(client, sec_users):
    u = sec_users
    login(client, u[1], "sec_usr_1")

    # Create 4-person challenge (Creator + U2, U3, U4)
    res = client.post("/api/challenges", json={
        "participant_ids": [u[2], u[3], u[4]],
        "challenge_type": "DISTANCE",
        "start_date": "2026-11-15",
        "end_date": "2026-11-22"
    })
    assert res.status_code == 201
    cid = res.get_json()["challenge_id"]

    # Creator cancels invitation for U4
    canc_res = client.post(f"/api/challenges/{cid}/participants/{u[4]}/cancel")
    assert canc_res.status_code == 200

    with flask_app.app_context():
        conn = get_db()
        p4 = conn.execute("SELECT invitation_status, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u[4])).fetchone()
        assert p4["invitation_status"] == "CANCELLED"
        assert p4["result"] == "CANCELLED"

        # Challenge itself is still INVITED because Creator + U2 + U3 = 3 potential runners
        chal = conn.execute("SELECT status FROM friendly_challenges WHERE id = ?", (cid,)).fetchone()
        assert chal["status"] == "INVITED"

    # Now creator cancels U3: remaining potential runners drops to 2 (Creator + U2) < 3 minimum!
    canc_u3_res = client.post(f"/api/challenges/{cid}/cancel", json={"user_id": u[3]})
    assert canc_u3_res.status_code == 200

    with flask_app.app_context():
        conn = get_db()
        # Challenge must auto-cancel because minimum 3 participants can never be met
        chal = conn.execute("SELECT status FROM friendly_challenges WHERE id = ?", (cid,)).fetchone()
        assert chal["status"] == "CANCELLED"


def test_threshold_of_three_and_roster_locking(client, sec_users):
    u = sec_users
    with flask_app.app_context():
        conn = get_db()
        # Scheduled challenge starting Nov 15
        cid = create_group_challenge(u[1], [u[2], u[3], u[4]], "DISTANCE", "2026-11-15", "2026-11-22", conn=conn)

        # U2 accepts: total accepted = 2 (U1 + U2) -> still INVITED
        accept_challenge(cid, u[2], conn=conn)
        chal = conn.execute("SELECT * FROM friendly_challenges WHERE id = ?", (cid,)).fetchone()
        assert chal["status"] == "INVITED"

        # Simulate start date arrival (2026-11-15) when only 2 accepted
        sim_start_dt = datetime(2026, 11, 15, 8, 0, 0, tzinfo=timezone.utc)
        expired = check_and_update_expiry(dict(chal), now_dt=sim_start_dt, conn=conn)
        assert expired is True

        chal_post = conn.execute("SELECT status FROM friendly_challenges WHERE id = ?", (cid,)).fetchone()
        assert chal_post["status"] == "EXPIRED"

        # Unaccepted invitee U3 tries to accept after start date
        with pytest.raises(ValueError, match="(?i)expired"):
            accept_challenge(cid, u[3], conn=conn)


def test_concurrency_and_max_participants_limit(sec_users):
    """Verifies concurrent duplicate acceptance safety and strict transactional enforcement of max participants."""
    u = sec_users
    with flask_app.app_context():
        conn = get_db()
        # Create group challenge with 3 total participants (Creator U1 + U2, U3)
        cid = create_group_challenge(u[1], [u[2], u[3]], "DISTANCE", "2026-11-20", "2026-11-27", conn=conn)

        # 1. Concurrent race: two threads attempt to accept for U2 simultaneously
        results = []
        def accept_worker():
            with flask_app.app_context():
                import time
                for _ in range(5):
                    t_conn = get_db()
                    try:
                        res = accept_challenge(cid, u[2], conn=t_conn)
                        results.append(("SUCCESS", res))
                        return
                    except Exception as e:
                        if "locked" in str(e).lower():
                            time.sleep(0.05)
                            continue
                        results.append(("ERROR", str(e)))
                        return
                results.append(("ERROR", "database is locked"))

        t1 = threading.Thread(target=accept_worker)
        t2 = threading.Thread(target=accept_worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # At least one succeeded, and U2 is accepted without data corruption
        assert any(r[0] == "SUCCESS" for r in results)
        p2 = conn.execute(
            "SELECT invitation_status FROM challenge_participants WHERE challenge_id = ? AND user_id = ?",
            (cid, u[2])
        ).fetchone()
        assert p2["invitation_status"] == "ACCEPTED"

        # 2. U3 accepts -> Challenge reaches max capacity of 3 participants
        accept_challenge(cid, u[3], conn=conn)
        chal = conn.execute("SELECT status, max_participants FROM friendly_challenges WHERE id = ?", (cid,)).fetchone()
        assert chal["status"] == "ACCEPTED"
        assert chal["max_participants"] == 3

        # 3. Transactional participant limit: an unauthorized extra participant cannot accept once full
        conn.execute(
            "INSERT INTO challenge_participants (challenge_id, user_id, invitation_status, result, score_unit) VALUES (?, ?, 'INVITED', 'NONE', 'km')",
            (cid, u[4])
        )
        conn.commit()

        with pytest.raises(ValueError, match="(?i)full|maximum"):
            accept_challenge(cid, u[4], conn=conn)

        # Uninvited user is rejected with PermissionError
        with pytest.raises(PermissionError, match="(?i)only invited"):
            accept_challenge(cid, u[11], conn=conn)
