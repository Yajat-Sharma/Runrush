"""
RunRush Friendly Challenges V2 - Group Finalization and Medal Integration Tests

Verifies:
1. Unique winner earns exactly 1 medal increment.
2. Tie for first results in a DRAW and NO medal.
3. Zero-score draw results in a DRAW and NO medal.
4. Multiple tied ranks lower down (e.g. 1st unique, 2nd tied) -> only 1st gets medal.
5. Participation alone does not earn a medal.
6. Repeated finalization is strictly idempotent.
7. Concurrent finalization is safe and idempotent.
8. Run edit recalculates challenge and transfers medal award with audit record.
9. Run deletion recalculates challenge to DRAW and revokes medal award.
10. Preserves V1 1v1 medal counts and results alongside group challenges.
"""

import concurrent.futures
from datetime import datetime, timezone
import json
import pytest

from app import app as flask_app
from db import get_db
from services.friendly_challenge_service import (
    create_friendly_challenge_tables,
    create_group_challenge,
    create_challenge,
    accept_challenge,
    finalize_challenge_if_due,
    recalibrate_user_challenges_on_run_change,
    get_user_friendly_challenge_stats,
    get_friendly_challenge_medal,
)


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
        (user_id, date_str, distance_km, time_min),
    )
    conn.commit()
    row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
    return row["id"] if row else None


def _delete_run(conn, run_id):
    conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
    conn.commit()


@pytest.fixture(autouse=True)
def clean_db(app):
    with app.app_context():
        create_friendly_challenge_tables()
        conn = get_db()
        conn.execute("DELETE FROM challenge_activity")
        conn.execute("DELETE FROM challenge_awards")
        conn.execute("DELETE FROM challenge_participants")
        conn.execute("DELETE FROM friendly_challenges")
        conn.execute("DELETE FROM runs WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'gf_%')")
        conn.execute("DELETE FROM users WHERE username LIKE 'gf_%'")
        conn.commit()
        yield


def test_unique_winner_earns_one_medal():
    """A unique first-place participant wins one medal increment; losers earn none."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "gf_u1")
        u2 = _create_user(conn, "gf_u2")
        u3 = _create_user(conn, "gf_u3")
        u4 = _create_user(conn, "gf_u4")

        cid = create_group_challenge(u1, [u2, u3, u4], "DISTANCE", "2026-11-02", "2026-11-08", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)
        accept_challenge(cid, u4, conn=conn)

        _add_run(conn, u1, 20.0, "2026-11-02")
        _add_run(conn, u2, 15.0, "2026-11-03")
        _add_run(conn, u3, 10.0, "2026-11-04")
        _add_run(conn, u4, 5.0, "2026-11-05")

        future_dt = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
        finalized = finalize_challenge_if_due(cid, now_dt=future_dt, conn=conn)

        assert finalized["status"] == "COMPLETED"
        assert finalized["result_type"] == "WIN"
        assert finalized["winner_id"] == u1

        # Check participants table
        p1 = conn.execute("SELECT rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u1)).fetchone()
        p2 = conn.execute("SELECT rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u2)).fetchone()
        p3 = conn.execute("SELECT rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u3)).fetchone()
        p4 = conn.execute("SELECT rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u4)).fetchone()

        assert p1["rank"] == 1 and p1["result"] == "WIN"
        assert p2["rank"] == 2 and p2["result"] == "LOSS"
        assert p3["rank"] == 3 and p3["result"] == "LOSS"
        assert p4["rank"] == 4 and p4["result"] == "LOSS"

        # Check awards table: only U1 gets 1 medal
        awards = conn.execute("SELECT user_id, award_type, rank FROM challenge_awards WHERE challenge_id = ?", (cid,)).fetchall()
        assert len(awards) == 1
        assert awards[0]["user_id"] == u1
        assert awards[0]["award_type"] == "FRIENDLY_CHALLENGE_WIN"
        assert awards[0]["rank"] == 1

        # Check user stats & medal badge
        s1 = get_user_friendly_challenge_stats(u1, conn=conn)
        s2 = get_user_friendly_challenge_stats(u2, conn=conn)
        assert s1["wins"] == 1 and s1["losses"] == 0 and s1["draws"] == 0 and s1["medal_count"] == 1
        assert s2["wins"] == 0 and s2["losses"] == 1 and s2["draws"] == 0 and s2["medal_count"] == 0

        m1 = get_friendly_challenge_medal(u1, conn=conn)
        assert m1["earned"] is True
        assert m1["count"] == 1


def test_tie_for_first_is_draw_and_no_medal():
    """A tie for first place results in a DRAW and NO medal is awarded to anyone."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "gf_t1")
        u2 = _create_user(conn, "gf_t2")
        u3 = _create_user(conn, "gf_t3")

        cid = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-02", "2026-11-08", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)

        # U1 and U2 tie at 12 km; U3 has 8 km
        _add_run(conn, u1, 12.0, "2026-11-02")
        _add_run(conn, u2, 12.0, "2026-11-03")
        _add_run(conn, u3, 8.0, "2026-11-04")

        future_dt = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
        finalized = finalize_challenge_if_due(cid, now_dt=future_dt, conn=conn)

        assert finalized["status"] == "COMPLETED"
        assert finalized["result_type"] == "DRAW"
        assert finalized["winner_id"] is None

        # Check participant results
        p1 = conn.execute("SELECT rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u1)).fetchone()
        p2 = conn.execute("SELECT rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u2)).fetchone()
        p3 = conn.execute("SELECT rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u3)).fetchone()

        assert p1["rank"] == 1 and p1["result"] == "DRAW"
        assert p2["rank"] == 1 and p2["result"] == "DRAW"
        assert p3["rank"] == 3 and p3["result"] == "LOSS"

        # Check awards: ZERO medals awarded
        awards = conn.execute("SELECT * FROM challenge_awards WHERE challenge_id = ?", (cid,)).fetchall()
        assert len(awards) == 0

        # Stats check
        s1 = get_user_friendly_challenge_stats(u1, conn=conn)
        s2 = get_user_friendly_challenge_stats(u2, conn=conn)
        s3 = get_user_friendly_challenge_stats(u3, conn=conn)
        assert s1["draws"] == 1 and s1["medal_count"] == 0
        assert s2["draws"] == 1 and s2["medal_count"] == 0
        assert s3["losses"] == 1 and s3["medal_count"] == 0


def test_zero_score_draw_earns_no_medal():
    """If all participants have 0 score, challenge ends in DRAW and no medals are awarded."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "gf_z1")
        u2 = _create_user(conn, "gf_z2")
        u3 = _create_user(conn, "gf_z3")

        cid = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-02", "2026-11-08", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)

        # No runs logged by anyone
        future_dt = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
        finalized = finalize_challenge_if_due(cid, now_dt=future_dt, conn=conn)

        assert finalized["status"] == "COMPLETED"
        assert finalized["result_type"] == "DRAW"
        assert finalized["winner_id"] is None

        p1 = conn.execute("SELECT rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u1)).fetchone()
        p2 = conn.execute("SELECT rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u2)).fetchone()
        p3 = conn.execute("SELECT rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u3)).fetchone()

        assert p1["rank"] == 1 and p1["result"] == "DRAW"
        assert p2["rank"] == 1 and p2["result"] == "DRAW"
        assert p3["rank"] == 1 and p3["result"] == "DRAW"

        awards = conn.execute("SELECT * FROM challenge_awards WHERE challenge_id = ?", (cid,)).fetchall()
        assert len(awards) == 0


def test_multiple_tied_ranks_lower_down():
    """Competition ranking with lower rank ties: 1st unique gets medal, tied 2nds get LOSS and no medal."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "gf_mr1")
        u2 = _create_user(conn, "gf_mr2")
        u3 = _create_user(conn, "gf_mr3")
        u4 = _create_user(conn, "gf_mr4")

        cid = create_group_challenge(u1, [u2, u3, u4], "DISTANCE", "2026-11-02", "2026-11-08", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)
        accept_challenge(cid, u4, conn=conn)

        _add_run(conn, u1, 25.0, "2026-11-02")
        _add_run(conn, u2, 18.0, "2026-11-02")
        _add_run(conn, u3, 18.0, "2026-11-03")
        _add_run(conn, u4, 10.0, "2026-11-04")

        future_dt = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
        finalized = finalize_challenge_if_due(cid, now_dt=future_dt, conn=conn)

        assert finalized["status"] == "COMPLETED"
        assert finalized["result_type"] == "WIN"
        assert finalized["winner_id"] == u1

        p1 = conn.execute("SELECT rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u1)).fetchone()
        p2 = conn.execute("SELECT rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u2)).fetchone()
        p3 = conn.execute("SELECT rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u3)).fetchone()
        p4 = conn.execute("SELECT rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u4)).fetchone()

        assert p1["rank"] == 1 and p1["result"] == "WIN"
        assert p2["rank"] == 2 and p2["result"] == "LOSS"
        assert p3["rank"] == 2 and p3["result"] == "LOSS"
        assert p4["rank"] == 4 and p4["result"] == "LOSS"

        awards = conn.execute("SELECT user_id FROM challenge_awards WHERE challenge_id = ?", (cid,)).fetchall()
        assert len(awards) == 1
        assert awards[0]["user_id"] == u1


def test_participation_alone_does_not_earn_medal():
    """Completing runs and participating in a group challenge does not grant a medal unless winning."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "gf_p1")
        u2 = _create_user(conn, "gf_p2")
        u3 = _create_user(conn, "gf_p3")

        cid = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-02", "2026-11-08", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)

        _add_run(conn, u1, 30.0, "2026-11-02")
        _add_run(conn, u2, 25.0, "2026-11-03")
        _add_run(conn, u3, 20.0, "2026-11-04")

        future_dt = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
        finalize_challenge_if_due(cid, now_dt=future_dt, conn=conn)

        stats_u2 = get_user_friendly_challenge_stats(u2, conn=conn)
        stats_u3 = get_user_friendly_challenge_stats(u3, conn=conn)

        assert stats_u2["participated"] == 1 and stats_u2["medal_count"] == 0
        assert stats_u3["participated"] == 1 and stats_u3["medal_count"] == 0


def test_repeated_finalization_is_idempotent():
    """Calling finalize_challenge_if_due multiple times produces identical state and no duplicate medals."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "gf_id1")
        u2 = _create_user(conn, "gf_id2")
        u3 = _create_user(conn, "gf_id3")

        cid = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-02", "2026-11-08", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)

        _add_run(conn, u1, 15.0, "2026-11-02")
        _add_run(conn, u2, 10.0, "2026-11-03")

        future_dt = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)

        # First finalization
        res1 = finalize_challenge_if_due(cid, now_dt=future_dt, conn=conn)
        assert res1["status"] == "COMPLETED"
        assert res1["winner_id"] == u1

        cnt1 = conn.execute("SELECT COUNT(*) AS cnt FROM challenge_awards WHERE challenge_id = ?", (cid,)).fetchone()["cnt"]
        assert cnt1 == 1

        # Second finalization (idempotent call)
        res2 = finalize_challenge_if_due(cid, now_dt=future_dt, conn=conn)
        assert res2["status"] == "COMPLETED"
        assert res2["winner_id"] == u1

        cnt2 = conn.execute("SELECT COUNT(*) AS cnt FROM challenge_awards WHERE challenge_id = ?", (cid,)).fetchone()["cnt"]
        assert cnt2 == 1

        # Third finalization
        res3 = finalize_challenge_if_due(cid, now_dt=future_dt, conn=conn)
        cnt3 = conn.execute("SELECT COUNT(*) AS cnt FROM challenge_awards WHERE challenge_id = ?", (cid,)).fetchone()["cnt"]
        assert cnt3 == 1


def test_concurrent_finalization_is_safe():
    """Multiple threads attempting to finalize the same challenge simultaneously execute safely without duplicates."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "gf_cf1")
        u2 = _create_user(conn, "gf_cf2")
        u3 = _create_user(conn, "gf_cf3")

        cid = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-02", "2026-11-08", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)

        _add_run(conn, u1, 20.0, "2026-11-02")
        _add_run(conn, u2, 10.0, "2026-11-03")

        future_dt = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)

        def _finalize_worker():
            with flask_app.app_context():
                import time
                for _ in range(5):
                    try:
                        return finalize_challenge_if_due(cid, now_dt=future_dt)
                    except Exception as e:
                        if "locked" in str(e).lower():
                            time.sleep(0.05)
                            continue
                        raise

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(_finalize_worker) for _ in range(4)]
            results = [f.result() for f in futures]

        for r in results:
            assert r["status"] == "COMPLETED"
            assert r["winner_id"] == u1

        # Awards table must have exactly 1 record for U1
        awards = conn.execute("SELECT * FROM challenge_awards WHERE challenge_id = ?", (cid,)).fetchall()
        assert len(awards) == 1
        assert awards[0]["user_id"] == u1


def test_run_edit_recalculates_and_transfers_award():
    """Editing a run recalculates the challenge, revokes prior award, awards new winner, and logs RECALIBRATED audit."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "gf_re1")
        u2 = _create_user(conn, "gf_re2")
        u3 = _create_user(conn, "gf_re3")

        cid = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-02", "2026-11-08", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)

        # Initially U1 runs 10 km, U2 runs 8 km, U3 runs 5 km -> U1 wins
        _add_run(conn, u1, 10.0, "2026-11-02")
        r2 = _add_run(conn, u2, 8.0, "2026-11-02")
        _add_run(conn, u3, 5.0, "2026-11-02")

        future_dt = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
        finalize_challenge_if_due(cid, now_dt=future_dt, conn=conn)

        # U1 holds award
        a1 = conn.execute("SELECT 1 FROM challenge_awards WHERE challenge_id = ? AND user_id = ?", (cid, u1)).fetchone()
        a2 = conn.execute("SELECT 1 FROM challenge_awards WHERE challenge_id = ? AND user_id = ?", (cid, u2)).fetchone()
        assert a1 is not None and a2 is None

        # U2 edits run from 8 km to 15 km (overtaking U1)
        conn.execute("UPDATE runs SET distance_km = 15.0 WHERE id = ?", (r2,))
        conn.commit()

        # Recalibrate
        recalibrate_user_challenges_on_run_change(u2, "2026-11-02", conn=conn)

        # Check friendly_challenges row
        chal_after = conn.execute("SELECT winner_id, result_type FROM friendly_challenges WHERE id = ?", (cid,)).fetchone()
        assert chal_after["winner_id"] == u2
        assert chal_after["result_type"] == "WIN"

        # Check awards: U1 revoked, U2 awarded
        a1_after = conn.execute("SELECT 1 FROM challenge_awards WHERE challenge_id = ? AND user_id = ?", (cid, u1)).fetchone()
        a2_after = conn.execute("SELECT 1 FROM challenge_awards WHERE challenge_id = ? AND user_id = ?", (cid, u2)).fetchone()
        assert a1_after is None, "Previous winner U1 must have award revoked"
        assert a2_after is not None, "New winner U2 must receive award"

        # Check audit record
        act = conn.execute("""
            SELECT * FROM challenge_activity
            WHERE challenge_id = ? AND activity_type = 'RECALIBRATED'
            ORDER BY id DESC LIMIT 1
        """, (cid,)).fetchone()
        assert act is not None
        meta = json.loads(act["metadata"])
        assert meta["challenge_mode"] == "GROUP"
        assert meta["old_winner_id"] == u1
        assert meta["new_winner_id"] == u2


def test_run_deletion_recalculates_to_draw_and_revokes_award():
    """Deleting a run turns a victory into a tie, revoking the medal and updating result to DRAW."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "gf_rd1")
        u2 = _create_user(conn, "gf_rd2")
        u3 = _create_user(conn, "gf_rd3")

        cid = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-02", "2026-11-08", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)

        # U1 has two runs: 8 km and 4 km (total 12 km); U2 has 8 km; U3 has 5 km
        _add_run(conn, u1, 8.0, "2026-11-02")
        r1_extra = _add_run(conn, u1, 4.0, "2026-11-03")
        _add_run(conn, u2, 8.0, "2026-11-02")
        _add_run(conn, u3, 5.0, "2026-11-02")

        future_dt = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
        finalize_challenge_if_due(cid, now_dt=future_dt, conn=conn)

        # U1 is winner with 1 medal
        assert conn.execute("SELECT 1 FROM challenge_awards WHERE challenge_id = ? AND user_id = ?", (cid, u1)).fetchone() is not None

        # Now U1 deletes the 4 km run, leaving U1 at 8 km (tied with U2 at 8 km)
        _delete_run(conn, r1_extra)
        recalibrate_user_challenges_on_run_change(u1, "2026-11-03", conn=conn)

        # Check challenge status
        chal_after = conn.execute("SELECT winner_id, result_type FROM friendly_challenges WHERE id = ?", (cid,)).fetchone()
        assert chal_after["winner_id"] is None
        assert chal_after["result_type"] == "DRAW"

        # Check participants
        p1 = conn.execute("SELECT rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u1)).fetchone()
        p2 = conn.execute("SELECT rank, result FROM challenge_participants WHERE challenge_id = ? AND user_id = ?", (cid, u2)).fetchone()
        assert p1["rank"] == 1 and p1["result"] == "DRAW"
        assert p2["rank"] == 1 and p2["result"] == "DRAW"

        # All awards revoked
        awards_after = conn.execute("SELECT * FROM challenge_awards WHERE challenge_id = ?", (cid,)).fetchall()
        assert len(awards_after) == 0

        # Audit record created
        act = conn.execute("""
            SELECT * FROM challenge_activity
            WHERE challenge_id = ? AND activity_type = 'RECALIBRATED'
            ORDER BY id DESC LIMIT 1
        """, (cid,)).fetchone()
        assert act is not None
        meta = json.loads(act["metadata"])
        assert meta["old_winner_id"] == u1
        assert meta["new_winner_id"] is None
        assert meta["new_result_type"] == "DRAW"


def test_preserves_v1_1v1_medal_counts_and_results():
    """Medal counts from 1v1 challenges and Group challenges accumulate accurately in challenge_awards."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "gf_v1_u1")
        u2 = _create_user(conn, "gf_v1_u2")
        u3 = _create_user(conn, "gf_v1_u3")

        # 1. Duel challenge: U1 vs U2
        cid_duel = create_challenge(u1, u2, "DISTANCE", "2026-11-08", "2026-11-10", conn=conn)
        accept_challenge(cid_duel, u2, conn=conn)
        _add_run(conn, u1, 10.0, "2026-11-09")
        _add_run(conn, u2, 5.0, "2026-11-09")

        finalize_challenge_if_due(cid_duel, now_dt=datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc), conn=conn)

        stats1 = get_user_friendly_challenge_stats(u1, conn=conn)
        assert stats1["medal_count"] == 1
        assert stats1["wins"] == 1

        # 2. Group challenge: U1, U2, U3
        cid_group = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-08", "2026-11-12", conn=conn)
        accept_challenge(cid_group, u2, conn=conn)
        accept_challenge(cid_group, u3, conn=conn)

        _add_run(conn, u1, 20.0, "2026-11-09")
        _add_run(conn, u2, 10.0, "2026-11-09")
        _add_run(conn, u3, 8.0, "2026-11-09")

        finalize_challenge_if_due(cid_group, now_dt=datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc), conn=conn)

        # U1 now has 2 medals total (1 from duel, 1 from group)
        stats2 = get_user_friendly_challenge_stats(u1, conn=conn)
        assert stats2["medal_count"] == 2
        assert stats2["wins"] == 2
        assert stats2["participated"] == 2

        # Verify medal badge reflects 2 medals
        medal_badge = get_friendly_challenge_medal(u1, conn=conn)
        assert medal_badge["earned"] is True
        assert medal_badge["count"] == 2
        assert "Friendly Challenges × 2" in medal_badge["name"]
