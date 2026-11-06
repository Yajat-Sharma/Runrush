"""
Tests for Friendly Challenges Phase 2: Player Discovery and Challenge Creation.
Tests the endpoints:
- GET /api/challenges/players
- POST /api/challenges
"""

import pytest
import os
import sys
import json
from datetime import datetime, date, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["DATABASE_URL"] = "sqlite:///test_runs.db"
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci")

from app import app as flask_app
from db import get_db
from services.friendly_challenge_service import create_friendly_challenge_tables


@pytest.fixture
def auth_users(app):
    """Creates two test users and returns their credentials and IDs."""
    with app.app_context():
        create_friendly_challenge_tables()
        conn = get_db()
        conn.execute("DELETE FROM challenge_awards")
        conn.execute("DELETE FROM challenge_activity")
        conn.execute("DELETE FROM challenge_participants")
        conn.execute("DELETE FROM friendly_challenges")
        conn.execute("DELETE FROM user_notifications")
        conn.execute("DELETE FROM notifications")
        conn.execute("DELETE FROM friends")
        conn.execute("DELETE FROM users WHERE username IN ('p2_runner_a', 'p2_runner_b', 'p2_blocked_user', 'p2_runner_c')")
        
        # User A
        conn.execute(
            "INSERT INTO users (username, pin, display_name, profile_emoji, status) VALUES (?, ?, ?, ?, 'active')",
            ("p2_runner_a", "dummy", "Runner Alpha", "🏃‍♂️")
        )
        # User B
        conn.execute(
            "INSERT INTO users (username, pin, display_name, profile_emoji, status) VALUES (?, ?, ?, ?, 'active')",
            ("p2_runner_b", "dummy", "Runner Beta", "🏃‍♀️")
        )
        # Blocked User
        conn.execute(
            "INSERT INTO users (username, pin, display_name, profile_emoji, status) VALUES (?, ?, ?, ?, 'blocked')",
            ("p2_blocked_user", "dummy", "Blocked Runner", "🚫")
        )
        # User C
        conn.execute(
            "INSERT INTO users (username, pin, display_name, profile_emoji, status) VALUES (?, ?, ?, ?, 'active')",
            ("p2_runner_c", "dummy", "Charlie Pace", "⚡")
        )
        conn.commit()

        u_a = conn.execute("SELECT id FROM users WHERE username = 'p2_runner_a'").fetchone()["id"]
        u_b = conn.execute("SELECT id FROM users WHERE username = 'p2_runner_b'").fetchone()["id"]
        u_blocked = conn.execute("SELECT id FROM users WHERE username = 'p2_blocked_user'").fetchone()["id"]
        u_c = conn.execute("SELECT id FROM users WHERE username = 'p2_runner_c'").fetchone()["id"]

        # User A follows User B
        conn.execute("INSERT INTO friends (follower_id, followed_id) VALUES (?, ?)", (u_a, u_b))
        conn.commit()

        return {
            "u_a": u_a,
            "u_b": u_b,
            "u_blocked": u_blocked,
            "u_c": u_c,
        }


# ---------------------------------------------------------------------------
# Player Discovery Tests
# ---------------------------------------------------------------------------

def test_player_search_requires_authentication(client):
    res = client.get("/api/challenges/players?q=runner")
    assert res.status_code == 401


def test_player_search_excludes_self_and_blocked(client, auth_users):
    with client.session_transaction() as sess:
        sess["user_id"] = auth_users["u_a"]

    res = client.get("/api/challenges/players")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"

    usernames = [p["username"] for p in data["players"]]
    # Self should not appear
    assert "p2_runner_a" not in usernames
    # Blocked user should not appear
    assert "p2_blocked_user" not in usernames
    # Other active users should appear
    assert "p2_runner_b" in usernames
    assert "p2_runner_c" in usernames


def test_player_search_by_username_and_display_name(client, auth_users):
    with client.session_transaction() as sess:
        sess["user_id"] = auth_users["u_a"]

    # Search by username prefix
    res = client.get("/api/challenges/players?q=p2_runner_b")
    data = res.get_json()
    assert len(data["players"]) == 1
    assert data["players"][0]["username"] == "p2_runner_b"
    assert data["players"][0]["is_following"] is True  # User A follows B

    # Search by display name
    res2 = client.get("/api/challenges/players?q=Charlie")
    data2 = res2.get_json()
    assert len(data2["players"]) == 1
    assert data2["players"][0]["username"] == "p2_runner_c"
    assert data2["players"][0]["is_following"] is False


def test_player_search_pagination(client, auth_users):
    with client.session_transaction() as sess:
        sess["user_id"] = auth_users["u_a"]

    res = client.get("/api/challenges/players?limit=1&page=1")
    data = res.get_json()
    assert len(data["players"]) == 1
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["limit"] == 1
    assert data["pagination"]["total"] >= 2
    assert data["pagination"]["has_next"] is True


# ---------------------------------------------------------------------------
# Challenge Creation & Validation Tests
# ---------------------------------------------------------------------------

def test_create_challenge_requires_authentication(client):
    res = client.post("/api/challenges", json={
        "opponent_id": 2,
        "challenge_type": "DISTANCE",
        "start_date": "2026-11-06",
        "end_date": "2026-11-13"
    })
    assert res.status_code == 401


def test_cannot_challenge_yourself(client, auth_users):
    with client.session_transaction() as sess:
        sess["user_id"] = auth_users["u_a"]

    res = client.post("/api/challenges", json={
        "opponent_id": auth_users["u_a"],
        "challenge_type": "DISTANCE",
        "start_date": "2026-11-06",
        "end_date": "2026-11-13"
    })
    assert res.status_code == 400
    assert "yourself" in res.get_json()["error"]


def test_cannot_challenge_blocked_or_nonexistent_user(client, auth_users):
    with client.session_transaction() as sess:
        sess["user_id"] = auth_users["u_a"]

    # Blocked user
    res1 = client.post("/api/challenges", json={
        "opponent_id": auth_users["u_blocked"],
        "challenge_type": "DISTANCE",
        "start_date": "2026-11-06",
        "end_date": "2026-11-13"
    })
    assert res1.status_code == 404

    # Nonexistent user
    res2 = client.post("/api/challenges", json={
        "opponent_id": 999999,
        "challenge_type": "DISTANCE",
        "start_date": "2026-11-06",
        "end_date": "2026-11-13"
    })
    assert res2.status_code == 404


def test_validates_challenge_types_and_date_ranges(client, auth_users):
    with client.session_transaction() as sess:
        sess["user_id"] = auth_users["u_a"]

    # Unsupported type
    res1 = client.post("/api/challenges", json={
        "opponent_id": auth_users["u_b"],
        "challenge_type": "SPRINT_BATTLE",
        "start_date": "2026-11-06",
        "end_date": "2026-11-13"
    })
    assert res1.status_code == 400

    # Start date after end date
    res2 = client.post("/api/challenges", json={
        "opponent_id": auth_users["u_b"],
        "challenge_type": "DISTANCE",
        "start_date": "2026-11-15",
        "end_date": "2026-11-10"
    })
    assert res2.status_code == 400
    assert "cannot be after" in res2.get_json()["error"]

    # Daily with unequal dates
    res3 = client.post("/api/challenges", json={
        "opponent_id": auth_users["u_b"],
        "challenge_type": "DAILY",
        "start_date": "2026-11-06",
        "end_date": "2026-11-07"
    })
    assert res3.status_code == 400
    assert "identical" in res3.get_json()["error"]


def test_successful_challenge_creation_and_notification(client, auth_users):
    with client.session_transaction() as sess:
        sess["user_id"] = auth_users["u_a"]

    res = client.post("/api/challenges", json={
        "opponent_id": auth_users["u_b"],
        "challenge_type": "DISTANCE",
        "start_date": "2026-11-06",
        "end_date": "2026-11-13",
        "title": "Weekly Mileage Clash",
        "message": "Let's see who puts in the miles!"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["status"] == "success"
    challenge_id = data["challenge_id"]
    assert challenge_id is not None

    with flask_app.app_context():
        conn = get_db()
        # Verify challenge record in DB
        chal = conn.execute("SELECT * FROM friendly_challenges WHERE id = ?", (challenge_id,)).fetchone()
        assert chal["status"] == "INVITED"
        assert chal["challenger_id"] == auth_users["u_a"]
        assert chal["opponent_id"] == auth_users["u_b"]
        assert chal["title"] == "Weekly Mileage Clash"

        # Verify notification was created for opponent B
        notif = conn.execute("""
            SELECT n.title, n.message, n.type
            FROM notifications n
            JOIN user_notifications un ON n.id = un.notification_id
            WHERE un.user_id = ?
        """, (auth_users["u_b"],)).fetchone()
        assert notif is not None
        assert "Challenge" in notif["title"]
        assert notif["type"] == "CHALLENGE_INVITATION"


def test_prevents_duplicate_pending_invitations(client, auth_users):
    with client.session_transaction() as sess:
        sess["user_id"] = auth_users["u_a"]

    # First invitation
    res1 = client.post("/api/challenges", json={
        "opponent_id": auth_users["u_b"],
        "challenge_type": "DISTANCE",
        "start_date": "2026-11-06",
        "end_date": "2026-11-13"
    })
    assert res1.status_code == 201

    # Second invitation while first is still pending
    res2 = client.post("/api/challenges", json={
        "opponent_id": auth_users["u_b"],
        "challenge_type": "CONSISTENCY",
        "start_date": "2026-11-06",
        "end_date": "2026-11-13"
    })
    assert res2.status_code == 409
    assert "already have a pending challenge" in res2.get_json()["error"]

    # Opponent also cannot send inverse invitation while one is pending
    with client.session_transaction() as sess:
        sess["user_id"] = auth_users["u_b"]

    res3 = client.post("/api/challenges", json={
        "opponent_id": auth_users["u_a"],
        "challenge_type": "DISTANCE",
        "start_date": "2026-11-06",
        "end_date": "2026-11-13"
    })
    assert res3.status_code == 409


def test_player_discovery_flags_pending_challenge(client, auth_users):
    with client.session_transaction() as sess:
        sess["user_id"] = auth_users["u_a"]

    # Send challenge to B
    client.post("/api/challenges", json={
        "opponent_id": auth_users["u_b"],
        "challenge_type": "DISTANCE",
        "start_date": "2026-11-06",
        "end_date": "2026-11-13"
    })

    # Search players
    res = client.get("/api/challenges/players?q=p2_runner_b")
    data = res.get_json()
    player_b = data["players"][0]
    assert player_b["has_pending_challenge"] is True
    assert player_b["pending_challenge_id"] is not None
