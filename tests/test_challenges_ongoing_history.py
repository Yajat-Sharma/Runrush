"""
Tests for RunRush Friendly Challenges Phase 4: Ongoing Progress UI & History.
Covers:
- GET /api/challenges/ongoing
- GET /api/challenges/<id>/progress
- GET /api/challenges/history (pagination & filtering)
- Real-time score calculations, ratio comparisons, leader status
- Qualifying run list aggregation
- Activity history logs
- Strict participant isolation
"""

from datetime import datetime, timedelta, timezone
import pytest
from app import app
from db import get_db
from services.friendly_challenge_service import (
    create_friendly_challenge_tables,
    create_challenge,
    accept_challenge,
    finalize_challenge_if_due,
)


@pytest.fixture(autouse=True)
def setup_challenge_db(app):
    """Ensure in-memory SQLite tables exist."""
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


def insert_run(user_id, date_str, distance_km, time_min=30.0, run_type="gps"):
    conn = get_db()
    conn.execute(
        "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type) "
        "VALUES (?, ?, ?, ?, '5:00', 300, ?)",
        (user_id, date_str, distance_km, time_min, run_type)
    )
    conn.commit()
    conn.close()


def test_ongoing_requires_authentication(client):
    res = client.get("/api/challenges/ongoing")
    assert res.status_code == 401


def test_ongoing_returns_accepted_challenges_with_realtime_scores_and_ratio(client):
    u1 = create_user("speedster", "Speedster")
    u2 = create_user("marathoner", "Marathoner")

    today = datetime.now(timezone.utc).date()
    start_str = str(today)
    end_str = str(today + timedelta(days=7))

    conn = get_db()
    chal_id = create_challenge(u1, u2, "DISTANCE", start_str, end_str, tz_name="UTC", title="10K Clash", conn=conn)
    accept_challenge(chal_id, u2, conn=conn)
    conn.close()

    # Insert runs for u1 (10km total) and u2 (5km total)
    insert_run(u1, str(today), 6.0)
    insert_run(u1, str(today), 4.0)
    insert_run(u2, str(today), 5.0)

    # Request ongoing challenges as u1
    with client.session_transaction() as sess:
        sess["user_id"] = u1

    res = client.get("/api/challenges/ongoing")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert len(data["challenges"]) == 1

    c = data["challenges"][0]
    assert c["id"] == chal_id
    assert c["title"] == "10K Clash"
    assert c["challenge_type"] == "DISTANCE"
    assert c["my_score"] == 10.0
    assert c["opponent_score"] == 5.0
    assert c["leader"] == "you"
    assert c["score_diff"] == 5.0
    assert c["my_ratio"] == 66.7
    assert c["opponent_ratio"] == 33.3
    assert "day" in c["time_remaining"].lower()

    # Request ongoing challenges as u2 (viewpoint inverted)
    with client.session_transaction() as sess:
        sess["user_id"] = u2

    res2 = client.get("/api/challenges/ongoing")
    assert res2.status_code == 200
    c2 = res2.get_json()["challenges"][0]
    assert c2["my_score"] == 5.0
    assert c2["opponent_score"] == 10.0
    assert c2["leader"] == "opponent"
    assert c2["my_ratio"] == 33.3
    assert c2["opponent_ratio"] == 66.7


def test_progress_endpoint_requires_participant_membership(client):
    u1 = create_user("part_a", "Part A")
    u2 = create_user("part_b", "Part B")
    u3 = create_user("intruder", "Intruder")

    today = datetime.now(timezone.utc).date()
    conn = get_db()
    chal_id = create_challenge(u1, u2, "LONGEST", str(today), str(today + timedelta(days=7)), tz_name="UTC", conn=conn)
    accept_challenge(chal_id, u2, conn=conn)
    conn.close()

    # Intruder u3 cannot access progress
    with client.session_transaction() as sess:
        sess["user_id"] = u3

    res = client.get(f"/api/challenges/{chal_id}/progress")
    assert res.status_code == 403
    assert "participant" in res.get_json()["error"].lower()

    # Participant u1 can access
    with client.session_transaction() as sess:
        sess["user_id"] = u1

    res_auth = client.get(f"/api/challenges/{chal_id}/progress")
    assert res_auth.status_code == 200
    p = res_auth.get_json()["progress"]
    assert p["challenge"]["id"] == chal_id
    assert "activity" in p
    assert "challenger" in p
    assert "opponent" in p


def test_progress_endpoint_returns_qualifying_runs_and_activity(client):
    u1 = create_user("racer_1", "Racer One")
    u2 = create_user("racer_2", "Racer Two")

    today = datetime.now(timezone.utc).date()
    conn = get_db()
    chal_id = create_challenge(u1, u2, "CONSISTENCY", str(today), str(today + timedelta(days=5)), tz_name="UTC", conn=conn)
    accept_challenge(chal_id, u2, conn=conn)
    conn.close()

    insert_run(u1, str(today), 5.5, run_type="gps")
    insert_run(u2, str(today), 4.2, run_type="manual")

    with client.session_transaction() as sess:
        sess["user_id"] = u1

    res = client.get(f"/api/challenges/{chal_id}/progress")
    assert res.status_code == 200
    data = res.get_json()["progress"]

    # Qualifying runs
    c_runs = data["challenger"]["qualifying_runs"]
    assert len(c_runs) == 1
    assert c_runs[0]["distance_km"] == 5.5
    assert c_runs[0]["run_type"] == "gps"

    o_runs = data["opponent"]["qualifying_runs"]
    assert len(o_runs) == 1
    assert o_runs[0]["distance_km"] == 4.2

    # Activity history contains CREATED and ACCEPTED
    activities = [a["activity_type"] for a in data["activity"]]
    assert "CREATED" in activities
    assert "ACCEPTED" in activities


def test_history_endpoint_filtering_and_pagination(client):
    u1 = create_user("hist_user", "History User")
    u2 = create_user("hist_rival", "History Rival")

    past_start = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
    past_end = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    conn = get_db()
    # 1. Completed challenge (accepted in the past and then finalized)
    c_comp = create_challenge(u1, u2, "DISTANCE", past_start, past_end, tz_name="UTC", title="Finished Duel", conn=conn)
    conn.execute("UPDATE friendly_challenges SET status = 'ACCEPTED' WHERE id = ?", (c_comp,))
    conn.commit()
    conn.close()

    insert_run(u1, past_start, 12.0)
    insert_run(u2, past_start, 8.0)

    # Finalize completed challenge
    conn = get_db()
    finalize_challenge_if_due(c_comp, conn=conn)

    # 2. Rejected challenge
    c_rej = create_challenge(u2, u1, "DAILY", str(datetime.now(timezone.utc).date()), str(datetime.now(timezone.utc).date()), tz_name="UTC", conn=conn)
    from services.friendly_challenge_service import reject_challenge
    reject_challenge(c_rej, u1, conn=conn)

    # 3. Cancelled challenge
    c_canc = create_challenge(u1, u2, "LONGEST", str(datetime.now(timezone.utc).date()), str(datetime.now(timezone.utc).date()), tz_name="UTC", conn=conn)
    from services.friendly_challenge_service import cancel_challenge
    cancel_challenge(c_canc, u1, conn=conn)
    conn.close()

    with client.session_transaction() as sess:
        sess["user_id"] = u1

    # Query all history
    res_all = client.get("/api/challenges/history")
    assert res_all.status_code == 200
    data_all = res_all.get_json()
    assert data_all["status"] == "success"
    assert len(data_all["challenges"]) == 3
    assert data_all["pagination"]["total"] == 3

    # Check outcomes
    outcomes = [c["outcome"] for c in data_all["challenges"]]
    assert "WIN" in outcomes  # u1 ran 12km vs 8km
    assert "DECLINED" in outcomes
    assert "CANCELLED" in outcomes

    # Filter completed
    res_comp = client.get("/api/challenges/history?filter=completed")
    assert res_comp.status_code == 200
    comp_list = res_comp.get_json()["challenges"]
    assert len(comp_list) == 1
    assert comp_list[0]["outcome"] == "WIN"
    assert comp_list[0]["my_final_score"] == 12.0
    assert comp_list[0]["opponent_final_score"] == 8.0

    # Filter declined
    res_declined = client.get("/api/challenges/history?filter=declined")
    assert res_declined.status_code == 200
    decl_list = res_declined.get_json()["challenges"]
    assert len(decl_list) == 1
    assert decl_list[0]["outcome"] == "DECLINED"
