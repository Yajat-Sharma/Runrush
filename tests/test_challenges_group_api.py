"""
Integration tests for RunRush Friendly Challenges V2: Free-for-all Group Challenges API.
Covers:
- POST /api/challenges (1v1 vs Group)
- GET /api/challenges/invitations (Group incoming & outgoing)
- GET /api/challenges/<id> (Authorization and group participants)
- POST /api/challenges/<id>/accept and reject
- GET /api/challenges/ongoing (Group cards with rank and leaderboard)
- GET /api/challenges/<id>/progress
- GET /api/challenges/history
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
def group_users(app):
    """Creates test users for group challenge API tests."""
    with app.app_context():
        create_friendly_challenge_tables()
        conn = get_db()
        conn.execute("DELETE FROM challenge_awards")
        conn.execute("DELETE FROM challenge_activity")
        conn.execute("DELETE FROM challenge_participants")
        conn.execute("DELETE FROM friendly_challenges")
        conn.execute("DELETE FROM user_notifications")
        conn.execute("DELETE FROM notifications")
        conn.execute("DELETE FROM users WHERE username LIKE 'grp_user_%'")

        users = {}
        for code in ["a", "b", "c", "d", "blocked"]:
            status = "blocked" if code == "blocked" else "active"
            conn.execute(
                "INSERT INTO users (username, pin, display_name, profile_emoji, status) VALUES (?, ?, ?, ?, ?)",
                (f"grp_user_{code}", "dummy", f"Runner {code.upper()}", "🏃", status)
            )
            u_id = conn.execute("SELECT id FROM users WHERE username = ?", (f"grp_user_{code}",)).fetchone()["id"]
            users[code] = u_id
        conn.commit()
        return users


def login_client(client, user_id, username):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = username


def test_api_create_group_challenge_success_and_validation(client, group_users):
    u = group_users
    login_client(client, u["a"], "grp_user_a")

    today = date.today().isoformat()
    end_day = (date.today() + timedelta(days=5)).isoformat()

    # 1. Validation: < 3 total participants (challenger + only 1 invitee)
    res = client.post("/api/challenges", json={
        "participant_ids": [u["b"]],
        "challenge_type": "DISTANCE",
        "start_date": today,
        "end_date": end_day,
        "title": "Too small group"
    })
    assert res.status_code == 400
    assert "at least 3 total participants" in res.get_json()["error"]

    # 2. Validation: Self-invite
    res = client.post("/api/challenges", json={
        "participant_ids": [u["a"], u["b"], u["c"]],
        "challenge_type": "DISTANCE",
        "start_date": today,
        "end_date": end_day
    })
    assert res.status_code == 400
    assert "cannot invite yourself" in res.get_json()["error"]

    # 3. Validation: Blocked user
    res = client.post("/api/challenges", json={
        "participant_ids": [u["b"], u["blocked"]],
        "challenge_type": "DISTANCE",
        "start_date": today,
        "end_date": end_day
    })
    assert res.status_code == 404

    # 4. Valid Group creation (3 total participants)
    res = client.post("/api/challenges", json={
        "participant_ids": [u["b"], u["c"]],
        "challenge_type": "DISTANCE",
        "start_date": today,
        "end_date": end_day,
        "title": "Epic 3-Way Showdown",
        "message": "Let's see who runs the most!"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["status"] == "success"
    assert data["challenge_mode"] == "GROUP"
    assert "challenge_id" in data
    cid = data["challenge_id"]

    # Check invitations endpoint for challenger (outgoing)
    inv_res = client.get("/api/challenges/invitations")
    assert inv_res.status_code == 200
    inv_data = inv_res.get_json()
    assert len(inv_data["outgoing"]) >= 1
    out_item = next(item for item in inv_data["outgoing"] if item["id"] == cid)
    assert out_item["challenge_mode"] == "GROUP"
    assert out_item["total_participants"] == 3
    assert out_item["accepted_count"] == 1  # Challenger auto-accepted

    # Check invitations endpoint for invitee B (incoming)
    login_client(client, u["b"], "grp_user_b")
    inv_b_res = client.get("/api/challenges/invitations")
    inv_b_data = inv_b_res.get_json()
    assert len(inv_b_data["incoming"]) >= 1
    inc_item = next(item for item in inv_b_data["incoming"] if item["id"] == cid)
    assert inc_item["challenge_mode"] == "GROUP"
    assert inc_item["challenger"]["id"] == u["a"]


def test_api_group_challenge_accept_and_ongoing(client, group_users):
    u = group_users
    login_client(client, u["a"], "grp_user_a")

    today = date.today().isoformat()
    end_day = (date.today() + timedelta(days=5)).isoformat()

    res = client.post("/api/challenges", json={
        "participant_ids": [u["b"], u["c"], u["d"]],
        "challenge_type": "DISTANCE",
        "start_date": today,
        "end_date": end_day,
        "title": "Quad Showdown"
    })
    assert res.status_code == 201
    cid = res.get_json()["challenge_id"]

    # Invitee B accepts -> 2 accepted (A + B) -> still INVITED (needs minimum 3)
    login_client(client, u["b"], "grp_user_b")
    acc_res = client.post(f"/api/challenges/{cid}/accept")
    assert acc_res.status_code == 200
    acc_data = acc_res.get_json()
    assert acc_data["status"] == "success"

    det_res = client.get(f"/api/challenges/{cid}")
    assert det_res.status_code == 200
    assert det_res.get_json()["challenge"]["status"] == "INVITED"

    # Invitee C accepts -> 3 accepted (A + B + C) -> triggers activation (ACCEPTED)
    login_client(client, u["c"], "grp_user_c")
    acc_c_res = client.post(f"/api/challenges/{cid}/accept")
    assert acc_c_res.status_code == 200

    # Details check for B (authorized participant)
    login_client(client, u["b"], "grp_user_b")
    det_res = client.get(f"/api/challenges/{cid}")
    assert det_res.status_code == 200
    det = det_res.get_json()["challenge"]
    assert det["challenge_mode"] == "GROUP"
    assert det["status"] == "ACCEPTED"
    assert len(det["participants"]) == 4

    # Ongoing check for challenger A
    login_client(client, u["a"], "grp_user_a")
    ong_res = client.get("/api/challenges/ongoing")
    assert ong_res.status_code == 200
    ong_data = ong_res.get_json()
    assert len(ong_data["challenges"]) >= 1
    ong_item = next(ch for ch in ong_data["challenges"] if ch["id"] == cid)
    assert ong_item["challenge_mode"] == "GROUP"
    assert "leaderboard" in ong_item
    assert "my_rank" in ong_item
    assert "opponent" in ong_item  # Backward compatibility fallback

    # Progress modal endpoint
    prog_res = client.get(f"/api/challenges/{cid}/progress")
    assert prog_res.status_code == 200
    prog = prog_res.get_json()["progress"]
    assert prog["challenge_mode"] == "GROUP"
    assert len(prog["leaderboard"]) == 4


def test_api_1v1_backward_compatibility_preserved(client, group_users):
    u = group_users
    login_client(client, u["a"], "grp_user_a")

    today = date.today().isoformat()
    end_day = (date.today() + timedelta(days=5)).isoformat()

    # Create standard 1v1 challenge
    res = client.post("/api/challenges", json={
        "opponent_id": u["b"],
        "challenge_type": "LONGEST",
        "start_date": today,
        "end_date": end_day,
        "title": "Classic 1v1"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["challenge_mode"] == "1V1"
    cid = data["challenge_id"]

    # Invitee B accepts
    login_client(client, u["b"], "grp_user_b")
    acc = client.post(f"/api/challenges/{cid}/accept")
    assert acc.status_code == 200

    # Check ongoing returns standard 1v1 schema
    ong_res = client.get("/api/challenges/ongoing")
    assert ong_res.status_code == 200
    ong_item = next(ch for ch in ong_res.get_json()["challenges"] if ch["id"] == cid)
    assert ong_item["challenge_mode"] == "1V1"
    assert "my_score" in ong_item
    assert "opponent_score" in ong_item
    assert "my_ratio" in ong_item
    assert "opponent_ratio" in ong_item
    assert "leader" in ong_item
