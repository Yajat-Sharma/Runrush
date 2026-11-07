"""
Tests for Phase 2: Free-for-all Group Challenges Service Layer.
Tests:
- Validation (3-10 participants, deduplication, self-invite rejection, type/date rules)
- Creation (1 challenger + N invitees)
- Independent acceptance and rejection
- Flexible start threshold (>= 2 accepted runners)
- Group progress leaderboard, rankings, and tie detection
- Group finalization with Shared Gold on 1st place ties
- Recalibration on run updates/deletions for group challenges
"""

import pytest
from datetime import datetime, date, timedelta, timezone
from app import app as flask_app
from db import get_db
from services.friendly_challenge_service import (
    create_friendly_challenge_tables,
    validate_group_challenge_params,
    create_group_challenge,
    accept_challenge,
    reject_challenge,
    get_challenge_progress,
    finalize_challenge_if_due,
    recalibrate_challenge_if_needed,
    recalibrate_user_challenges_on_run_change,
    get_user_friendly_challenge_stats,
)


@pytest.fixture(autouse=True)
def setup_group_db(app):
    with flask_app.app_context():
        create_friendly_challenge_tables()
        conn = get_db()
        conn.execute("DELETE FROM challenge_awards")
        conn.execute("DELETE FROM challenge_activity")
        conn.execute("DELETE FROM challenge_participants")
        conn.execute("DELETE FROM friendly_challenges")
        conn.execute("DELETE FROM runs")
        conn.execute("DELETE FROM users WHERE username LIKE 'grp_test_%'")
        conn.commit()


def _create_user(conn, username):
    conn.execute(
        "INSERT INTO users (username, pin, display_name) VALUES (?, 'pin', ?)",
        (username, f"Runner {username}"),
    )
    conn.commit()
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    return row["id"] if hasattr(row, "keys") else row[0]


def _add_run(conn, user_id, distance_km, date_str, time_min=30.0):
    conn.execute(
        "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type) "
        "VALUES (?, ?, ?, ?, 5.0, 300.0, 'easy')",
        (user_id, date_str, float(distance_km), float(time_min))
    )
    conn.commit()


def test_validate_group_params():
    # Valid 3 participants (1 creator + 2 invitees)
    p = validate_group_challenge_params(1, [2, 3], "DISTANCE", "2026-11-01", "2026-11-07")
    assert p["total_participants"] == 3
    assert p["invitee_ids"] == [2, 3]

    # Valid 10 participants (1 creator + 9 invitees)
    p10 = validate_group_challenge_params(1, list(range(2, 11)), "DISTANCE", "2026-11-01", "2026-11-07")
    assert p10["total_participants"] == 10

    # Underflow: < 3 participants
    with pytest.raises(ValueError, match="at least 3"):
        validate_group_challenge_params(1, [2], "DISTANCE", "2026-11-01", "2026-11-07")

    # Overflow: > 10 participants
    with pytest.raises(ValueError, match="at most 10"):
        validate_group_challenge_params(1, list(range(2, 12)), "DISTANCE", "2026-11-01", "2026-11-07")

    # Self-invitation rejection
    with pytest.raises(ValueError, match="Cannot invite yourself"):
        validate_group_challenge_params(1, [1, 2, 3], "DISTANCE", "2026-11-01", "2026-11-07")

    # Deduplication of invitee list
    p_dup = validate_group_challenge_params(1, [2, 2, 3, 3], "DISTANCE", "2026-11-01", "2026-11-07")
    assert p_dup["invitee_ids"] == [2, 3]
    assert p_dup["total_participants"] == 3


def test_create_group_challenge_records():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "grp_test_c1")
        u2 = _create_user(conn, "grp_test_c2")
        u3 = _create_user(conn, "grp_test_c3")
        u4 = _create_user(conn, "grp_test_c4")

        cid = create_group_challenge(u1, [u2, u3, u4], "DISTANCE", "2026-11-10", "2026-11-17", title="Nov Clash", conn=conn)
        assert cid is not None

        chal = conn.execute("SELECT * FROM friendly_challenges WHERE id = ?", (cid,)).fetchone()
        assert chal["challenge_mode"] == "GROUP"
        assert chal["max_participants"] == 4
        assert chal["status"] == "INVITED"

        participants = conn.execute("SELECT * FROM challenge_participants WHERE challenge_id = ? ORDER BY user_id", (cid,)).fetchall()
        assert len(participants) == 4

        # Challenger must be ACCEPTED
        p1 = [p for p in participants if p["user_id"] == u1][0]
        assert p1["invitation_status"] == "ACCEPTED"

        # Invitees must be INVITED
        for p in participants:
            if p["user_id"] != u1:
                assert p["invitation_status"] == "INVITED"


def test_group_challenge_acceptance_and_rejection():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "grp_test_a1")
        u2 = _create_user(conn, "grp_test_a2")
        u3 = _create_user(conn, "grp_test_a3")

        cid = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-10", "2026-11-17", conn=conn)

        # U2 accepts -> Total accepted becomes 2 (>= 2 threshold) -> challenge status becomes ACCEPTED
        accept_challenge(cid, u2, conn=conn)
        chal = conn.execute("SELECT status FROM friendly_challenges WHERE id = ?", (cid,)).fetchone()
        assert chal["status"] == "ACCEPTED"

        # U3 rejects -> U3 is marked REJECTED, but challenge remains ACCEPTED for U1 & U2
        reject_challenge(cid, u3, conn=conn)
        p3 = conn.execute("SELECT invitation_status, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u3)).fetchone()
        assert p3["invitation_status"] == "REJECTED"
        assert p3["result"] == "DECLINED"

        chal = conn.execute("SELECT status FROM friendly_challenges WHERE id = ?", (cid,)).fetchone()
        assert chal["status"] == "ACCEPTED"


def test_group_challenge_progress_leaderboard():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "grp_test_p1")
        u2 = _create_user(conn, "grp_test_p2")
        u3 = _create_user(conn, "grp_test_p3")

        cid = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-01", "2026-11-07", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)

        # Add runs
        _add_run(conn, u1, 10.0, "2026-11-02")
        _add_run(conn, u2, 15.5, "2026-11-03")
        _add_run(conn, u3, 8.0, "2026-11-04")

        progress = get_challenge_progress(cid, conn=conn)
        assert progress["challenge_mode"] == "GROUP"
        assert progress["total_participants"] == 3
        assert progress["accepted_count"] == 3
        assert progress["leader_id"] == u2
        assert progress["is_tied"] is False

        lb = progress["leaderboard"]
        assert len(lb) == 3
        assert lb[0]["user_id"] == u2
        assert lb[0]["rank"] == 1
        assert lb[0]["score"] == 15.5

        assert lb[1]["user_id"] == u1
        assert lb[1]["rank"] == 2

        assert lb[2]["user_id"] == u3
        assert lb[2]["rank"] == 3


def test_group_challenge_finalization_with_shared_gold():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "grp_test_f1")
        u2 = _create_user(conn, "grp_test_f2")
        u3 = _create_user(conn, "grp_test_f3")

        # Window: Nov 01 to Nov 07
        cid = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-01", "2026-11-07", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)

        # U1 and U2 tie for 1st with 12 km each; U3 runs 5 km
        _add_run(conn, u1, 12.0, "2026-11-02")
        _add_run(conn, u2, 12.0, "2026-11-03")
        _add_run(conn, u3, 5.0, "2026-11-04")

        # Finalize on Nov 08 (past end date)
        future_dt = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
        finalized = finalize_challenge_if_due(cid, now_dt=future_dt, conn=conn)
        assert finalized["status"] == "COMPLETED"
        assert finalized["result_type"] == "WIN"

        # Check participants
        p1 = conn.execute("SELECT final_score, rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u1)).fetchone()
        p2 = conn.execute("SELECT final_score, rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u2)).fetchone()
        p3 = conn.execute("SELECT final_score, rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u3)).fetchone()

        assert p1["rank"] == 1 and p1["result"] == "WIN"
        assert p2["rank"] == 1 and p2["result"] == "WIN"
        assert p3["rank"] == 3 and p3["result"] == "LOSS"

        # Check Shared Gold awards: both U1 and U2 receive 1 Friendly Challenges medal
        a1 = conn.execute("SELECT 1 FROM challenge_awards WHERE challenge_id = ? AND user_id = ?", (cid, u1)).fetchone()
        a2 = conn.execute("SELECT 1 FROM challenge_awards WHERE challenge_id = ? AND user_id = ?", (cid, u2)).fetchone()
        a3 = conn.execute("SELECT 1 FROM challenge_awards WHERE challenge_id = ? AND user_id = ?", (cid, u3)).fetchone()

        assert a1 is not None, "U1 tied for 1st should have award"
        assert a2 is not None, "U2 tied for 1st should have award"
        assert a3 is None, "U3 in 3rd place should not have award"


def test_group_challenge_recalibration_on_run_edit():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "grp_test_r1")
        u2 = _create_user(conn, "grp_test_r2")
        u3 = _create_user(conn, "grp_test_r3")

        cid = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-01", "2026-11-07", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)

        # U1 runs 10, U2 runs 8, U3 runs 5 -> U1 is sole winner
        _add_run(conn, u1, 10.0, "2026-11-02")
        _add_run(conn, u2, 8.0, "2026-11-02")
        _add_run(conn, u3, 5.0, "2026-11-02")

        future_dt = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
        finalize_challenge_if_due(cid, now_dt=future_dt, conn=conn)
        assert conn.execute("SELECT 1 FROM challenge_awards WHERE challenge_id = ? AND user_id = ?", (cid, u1)).fetchone() is not None
        assert conn.execute("SELECT 1 FROM challenge_awards WHERE challenge_id = ? AND user_id = ?", (cid, u2)).fetchone() is None

        # Now U2 logs/edits an extra 6 km run -> U2 now has 14 km (overtaking U1)
        _add_run(conn, u2, 6.0, "2026-11-03")
        recalibrate_user_challenges_on_run_change(u2, "2026-11-03", conn=conn)

        # Re-check awards
        a1 = conn.execute("SELECT 1 FROM challenge_awards WHERE challenge_id = ? AND user_id = ?", (cid, u1)).fetchone()
        a2 = conn.execute("SELECT 1 FROM challenge_awards WHERE challenge_id = ? AND user_id = ?", (cid, u2)).fetchone()
        assert a1 is None, "U1 is no longer winner so award should be revoked"
        assert a2 is not None, "U2 is new winner so award should be granted"
