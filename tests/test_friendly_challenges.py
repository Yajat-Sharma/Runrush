"""
Tests for Friendly Challenges V1 — Phase 1 Backend Foundation.
Tests schema migrations, deterministic calculations, timezone handling,
state transitions, tie detection, finalization, and award idempotency.
"""

import pytest
import os
import sys
from datetime import datetime, date, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["DATABASE_URL"] = "sqlite:///test_runs.db"
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci")

from app import app as flask_app, init_db
from db import get_db
from services.friendly_challenge_service import (
    create_friendly_challenge_tables,
    validate_challenge_params,
    parse_run_local_date,
    get_eligible_runs,
    calculate_score,
    compare_scores,
    create_challenge,
    accept_challenge,
    reject_challenge,
    cancel_challenge,
    check_and_update_expiry,
    get_challenge_progress,
    finalize_challenge_if_due,
    recalibrate_challenge_if_needed,
    get_user_friendly_challenge_stats,
)


@pytest.fixture(autouse=True)
def setup_test_db(app):
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    with flask_app.app_context():
        create_friendly_challenge_tables()
        conn = get_db()
        conn.execute("DELETE FROM challenge_awards")
        conn.execute("DELETE FROM challenge_activity")
        conn.execute("DELETE FROM challenge_participants")
        conn.execute("DELETE FROM friendly_challenges")
        conn.execute("DELETE FROM runs")
        conn.execute("DELETE FROM users WHERE username LIKE 'fc_test_%'")
        conn.commit()


def _create_user(conn, username):
    conn.execute(
        "INSERT INTO users (username, pin, display_name) VALUES (?, ?, ?)",
        (username, "dummy_hash", f"Runner {username}"),
    )
    conn.commit()
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    return row["id"] if hasattr(row, "keys") else row[0]


def _add_run(conn, user_id, distance_km, date_str, time_min=30.0):
    conn.execute(
        "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type) "
        "VALUES (?, ?, ?, ?, ?, ?, 'easy')",
        (user_id, date_str, float(distance_km), float(time_min), 5.0, 300.0)
    )
    conn.commit()
    row = conn.execute("SELECT id FROM runs WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    return row["id"] if hasattr(row, "keys") else row[0]


# ---------------------------------------------------------------------------
# 1. Migration on Existing Test DB
# ---------------------------------------------------------------------------

def test_migration_creates_tables_and_indexes():
    with flask_app.app_context():
        conn = get_db()
        create_friendly_challenge_tables(conn)

        # Verify tables exist by inserting/selecting
        u1 = _create_user(conn, "fc_test_mig_1")
        u2 = _create_user(conn, "fc_test_mig_2")
        chal_id = create_challenge(u1, u2, "DISTANCE", "2026-11-01", "2026-11-08", conn=conn)
        assert chal_id is not None

        participants = conn.execute(
            "SELECT * FROM challenge_participants WHERE challenge_id = ?", (chal_id,)
        ).fetchall()
        assert len(participants) == 2

        activities = conn.execute(
            "SELECT * FROM challenge_activity WHERE challenge_id = ?", (chal_id,)
        ).fetchall()
        assert len(activities) >= 1


# ---------------------------------------------------------------------------
# 2. Four Score Calculations & Multiple Runs on Same Day
# ---------------------------------------------------------------------------

def test_distance_calculation_and_multiple_runs_same_day():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "fc_test_dist_1")

        # 2 runs on the same day, 1 on another day
        _add_run(conn, u1, 5.25, "2026-11-02 08:00:00")
        _add_run(conn, u1, 4.75, "2026-11-02 18:00:00")
        _add_run(conn, u1, 10.0, "2026-11-03 09:00:00")

        runs = get_eligible_runs(conn, u1, "2026-11-01", "2026-11-07")
        assert len(runs) == 3

        score, unit = calculate_score(runs, "DISTANCE")
        assert unit == "km"
        assert abs(score - 20.0) < 1e-6


def test_consistency_calculation_multiple_runs_same_day():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "fc_test_cons_1")

        # 3 runs on 2 distinct days
        _add_run(conn, u1, 5.0, "2026-11-02 08:00:00")
        _add_run(conn, u1, 3.0, "2026-11-02 17:00:00")  # same day
        _add_run(conn, u1, 6.0, "2026-11-04 09:00:00")  # second day

        runs = get_eligible_runs(conn, u1, "2026-11-01", "2026-11-07")
        score, unit = calculate_score(runs, "CONSISTENCY")
        assert unit == "days"
        assert score == 2.0  # exactly 2 distinct days


def test_longest_individual_run_calculation():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "fc_test_long_1")

        _add_run(conn, u1, 4.5, "2026-11-02")
        _add_run(conn, u1, 15.8, "2026-11-03")
        _add_run(conn, u1, 10.2, "2026-11-04")

        runs = get_eligible_runs(conn, u1, "2026-11-01", "2026-11-07")
        score, unit = calculate_score(runs, "LONGEST")
        assert unit == "km"
        assert abs(score - 15.8) < 1e-6


def test_daily_distance_calculation():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "fc_test_daily_1")

        # Run on the day
        _add_run(conn, u1, 6.2, "2026-11-03 07:00:00")
        _add_run(conn, u1, 3.8, "2026-11-03 19:00:00")
        # Run on previous day and next day (should be excluded)
        _add_run(conn, u1, 10.0, "2026-11-02 10:00:00")
        _add_run(conn, u1, 12.0, "2026-11-04 10:00:00")

        runs = get_eligible_runs(conn, u1, "2026-11-03", "2026-11-03")
        assert len(runs) == 2
        score, unit = calculate_score(runs, "DAILY")
        assert unit == "km"
        assert abs(score - 10.0) < 1e-6


# ---------------------------------------------------------------------------
# 3. No Runs & Zero Score
# ---------------------------------------------------------------------------

def test_no_runs_returns_zero_score():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "fc_test_noruns_1")

        runs = get_eligible_runs(conn, u1, "2026-11-01", "2026-11-07")
        assert len(runs) == 0

        for c_type in ["DISTANCE", "CONSISTENCY", "LONGEST", "DAILY"]:
            score, unit = calculate_score(runs, c_type)
            assert score == 0.0


# ---------------------------------------------------------------------------
# 4. Equal Scores & Tie Detection
# ---------------------------------------------------------------------------

def test_equal_scores_tie_detection():
    assert compare_scores(10.0, 10.0) == 0
    assert compare_scores(10.000000001, 10.000000002) == 0
    assert compare_scores(10.5, 10.2) == 1
    assert compare_scores(8.1, 9.4) == -1


def test_finalization_with_draw_gives_no_awards():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "fc_test_tie_1")
        u2 = _create_user(conn, "fc_test_tie_2")

        # Both ran exactly 8.0 km
        _add_run(conn, u1, 8.0, "2026-11-02")
        _add_run(conn, u2, 8.0, "2026-11-03")

        chal_id = create_challenge(u1, u2, "DISTANCE", "2026-11-01", "2026-11-08", conn=conn)
        accept_challenge(chal_id, u2, conn=conn)

        # Finalize after end_date (e.g. on 2026-11-10)
        future_dt = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
        chal = finalize_challenge_if_due(chal_id, now_dt=future_dt, conn=conn)

        assert chal["status"] == "COMPLETED"
        assert chal["winner_id"] is None
        assert chal["result_type"] == "DRAW"

        # Check awards: neither participant received an award
        awards = conn.execute("SELECT * FROM challenge_awards WHERE challenge_id = ?", (chal_id,)).fetchall()
        assert len(awards) == 0

        # Check participants results
        cp = conn.execute("SELECT user_id, result, final_score FROM challenge_participants WHERE challenge_id = ?", (chal_id,)).fetchall()
        for p in cp:
            assert p["result"] == "DRAW"
            assert abs(p["final_score"] - 8.0) < 1e-6


# ---------------------------------------------------------------------------
# 5. Different Participant Data & Winner Determination
# ---------------------------------------------------------------------------

def test_winner_determination_and_participant_isolation():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "fc_test_win_1")
        u2 = _create_user(conn, "fc_test_win_2")

        _add_run(conn, u1, 12.0, "2026-11-02")
        _add_run(conn, u2, 7.5, "2026-11-02")

        chal_id = create_challenge(u1, u2, "DISTANCE", "2026-11-01", "2026-11-08", conn=conn)
        accept_challenge(chal_id, u2, conn=conn)

        future_dt = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
        chal = finalize_challenge_if_due(chal_id, now_dt=future_dt, conn=conn)

        assert chal["status"] == "COMPLETED"
        assert chal["winner_id"] == u1
        assert chal["result_type"] == "WIN"

        # Winner receives exactly 1 award
        awards = conn.execute("SELECT * FROM challenge_awards WHERE challenge_id = ?", (chal_id,)).fetchall()
        assert len(awards) == 1
        assert awards[0]["user_id"] == u1

        # Check stats helper
        stats_u1 = get_user_friendly_challenge_stats(u1, conn=conn)
        assert stats_u1["participated"] == 1
        assert stats_u1["wins"] == 1
        assert stats_u1["losses"] == 0
        assert stats_u1["draws"] == 0
        assert stats_u1["medal_count"] == 1

        stats_u2 = get_user_friendly_challenge_stats(u2, conn=conn)
        assert stats_u2["participated"] == 1
        assert stats_u2["wins"] == 0
        assert stats_u2["losses"] == 1
        assert stats_u2["draws"] == 0
        assert stats_u2["medal_count"] == 0


# ---------------------------------------------------------------------------
# 6. Date Boundaries (Strict Inclusivity)
# ---------------------------------------------------------------------------

def test_date_boundaries_inclusive():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "fc_test_bounds_1")

        _add_run(conn, u1, 10.0, "2026-11-01")  # day before: excluded
        _add_run(conn, u1, 5.0, "2026-11-02")   # start date: INCLUDED
        _add_run(conn, u1, 7.0, "2026-11-04")   # inside: INCLUDED
        _add_run(conn, u1, 3.0, "2026-11-05")   # end date: INCLUDED
        _add_run(conn, u1, 20.0, "2026-11-06")  # day after: excluded

        runs = get_eligible_runs(conn, u1, "2026-11-02", "2026-11-05")
        assert len(runs) == 3
        total_dist = sum(r["distance_km"] for r in runs)
        assert abs(total_dist - 15.0) < 1e-6


# ---------------------------------------------------------------------------
# 7. Timezone Boundaries
# ---------------------------------------------------------------------------

def test_timezone_boundaries_determination():
    # In America/New_York (UTC-5), 2026-11-06 02:00:00 UTC is 2026-11-05 21:00:00 (Nov 5th)
    parsed_date = parse_run_local_date("2026-11-06 02:00:00", tz_name="America/New_York")
    assert parsed_date == "2026-11-05"

    # In Asia/Tokyo (UTC+9), 2026-11-06 20:00:00 UTC is 2026-11-07 05:00:00 (Nov 7th)
    parsed_date_tokyo = parse_run_local_date("2026-11-06 20:00:00", tz_name="Asia/Tokyo")
    assert parsed_date_tokyo == "2026-11-07"


def test_challenge_evaluates_with_fixed_challenge_timezone():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "fc_test_tz_1")

        # Run logged at UTC 2026-11-06 02:00:00
        _add_run(conn, u1, 10.0, "2026-11-06 02:00:00")

        # Challenge configured with America/New_York ending on 2026-11-05
        runs_ny = get_eligible_runs(conn, u1, "2026-11-01", "2026-11-05", tz_name="America/New_York")
        assert len(runs_ny) == 1  # In NY it was Nov 5!

        # In UTC, that same run is Nov 6 (outside window)
        runs_utc = get_eligible_runs(conn, u1, "2026-11-01", "2026-11-05", tz_name="UTC")
        assert len(runs_utc) == 0


# ---------------------------------------------------------------------------
# 8. Edited and Deleted Runs
# ---------------------------------------------------------------------------

def test_dynamic_recalculation_on_edited_run():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "fc_test_edit_1")
        u2 = _create_user(conn, "fc_test_edit_2")

        run_id = _add_run(conn, u1, 10.0, "2026-11-03")
        _add_run(conn, u2, 8.0, "2026-11-03")

        chal_id = create_challenge(u1, u2, "DISTANCE", "2026-11-01", "2026-11-08", conn=conn)
        accept_challenge(chal_id, u2, conn=conn)

        progress = get_challenge_progress(chal_id, conn=conn)
        assert abs(progress["challenger"]["score"] - 10.0) < 1e-6
        assert progress["leader_id"] == u1

        # Now edit the run: reduce from 10.0 km to 6.0 km
        conn.execute("UPDATE runs SET distance_km = 6.0 WHERE id = ?", (run_id,))
        conn.commit()

        # Recalculates dynamically
        updated_progress = get_challenge_progress(chal_id, conn=conn)
        assert abs(updated_progress["challenger"]["score"] - 6.0) < 1e-6
        assert updated_progress["leader_id"] == u2  # Opponent is now leader!


def test_recalibrate_completed_challenge_on_deleted_run():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "fc_test_recal_1")
        u2 = _create_user(conn, "fc_test_recal_2")

        run1 = _add_run(conn, u1, 15.0, "2026-11-03")
        _add_run(conn, u2, 10.0, "2026-11-03")

        chal_id = create_challenge(u1, u2, "DISTANCE", "2026-11-01", "2026-11-08", conn=conn)
        accept_challenge(chal_id, u2, conn=conn)

        # Finalize challenge with u1 as winner
        future_dt = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
        finalize_challenge_if_due(chal_id, now_dt=future_dt, conn=conn)

        assert get_user_friendly_challenge_stats(u1, conn=conn)["medal_count"] == 1
        assert get_user_friendly_challenge_stats(u2, conn=conn)["medal_count"] == 0

        # Now delete u1's run!
        conn.execute("DELETE FROM runs WHERE id = ?", (run1,))
        conn.commit()

        # Recalibrate
        recalibrate_challenge_if_needed(chal_id, conn=conn)

        chal_after = conn.execute("SELECT * FROM friendly_challenges WHERE id = ?", (chal_id,)).fetchone()
        assert chal_after["winner_id"] == u2
        assert chal_after["result_type"] == "WIN"

        # Medal was transferred to u2 safely
        assert get_user_friendly_challenge_stats(u1, conn=conn)["medal_count"] == 0
        assert get_user_friendly_challenge_stats(u2, conn=conn)["medal_count"] == 1


# ---------------------------------------------------------------------------
# 9. Duplicate Award Prevention (Idempotency)
# ---------------------------------------------------------------------------

def test_duplicate_award_prevention():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "fc_test_idem_1")
        u2 = _create_user(conn, "fc_test_idem_2")

        _add_run(conn, u1, 10.0, "2026-11-02")
        _add_run(conn, u2, 5.0, "2026-11-02")

        chal_id = create_challenge(u1, u2, "DISTANCE", "2026-11-01", "2026-11-08", conn=conn)
        accept_challenge(chal_id, u2, conn=conn)

        future_dt = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
        # Call finalize multiple times
        finalize_challenge_if_due(chal_id, now_dt=future_dt, conn=conn)
        finalize_challenge_if_due(chal_id, now_dt=future_dt, conn=conn)
        finalize_challenge_if_due(chal_id, now_dt=future_dt, conn=conn)

        awards = conn.execute("SELECT * FROM challenge_awards WHERE challenge_id = ?", (chal_id,)).fetchall()
        assert len(awards) == 1
        assert awards[0]["user_id"] == u1


# ---------------------------------------------------------------------------
# 10. State Transitions, Expiry & Validation
# ---------------------------------------------------------------------------

def test_validation_rules():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "fc_test_val_1")
        u2 = _create_user(conn, "fc_test_val_2")

        # Self challenge
        with pytest.raises(ValueError, match="Cannot challenge yourself"):
            create_challenge(u1, u1, "DISTANCE", "2026-11-01", "2026-11-07", conn=conn)

        # Invalid type
        with pytest.raises(ValueError, match="Invalid challenge type"):
            create_challenge(u1, u2, "INVALID_TYPE", "2026-11-01", "2026-11-07", conn=conn)

        # Start date after end date
        with pytest.raises(ValueError, match="cannot be after end date"):
            create_challenge(u1, u2, "DISTANCE", "2026-11-10", "2026-11-07", conn=conn)

        # Daily with mismatched dates
        with pytest.raises(ValueError, match="identical start and end dates"):
            create_challenge(u1, u2, "DAILY", "2026-11-01", "2026-11-02", conn=conn)

        # Invalid timezone
        with pytest.raises(ValueError, match="Invalid IANA timezone"):
            create_challenge(u1, u2, "DISTANCE", "2026-11-01", "2026-11-07", tz_name="Invalid/TZ", conn=conn)


def test_invitation_lifecycle_accept_reject_cancel():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "fc_test_life_1")
        u2 = _create_user(conn, "fc_test_life_2")
        u3 = _create_user(conn, "fc_test_life_3")

        # 1. Accept
        chal1 = create_challenge(u1, u2, "DISTANCE", "2026-11-01", "2026-11-08", conn=conn)
        with pytest.raises(PermissionError):
            accept_challenge(chal1, u3, conn=conn)  # u3 is not opponent
        assert accept_challenge(chal1, u2, conn=conn) is True

        # 2. Reject
        chal2 = create_challenge(u1, u2, "DISTANCE", "2026-11-01", "2026-11-08", conn=conn)
        with pytest.raises(PermissionError):
            reject_challenge(chal2, u3, conn=conn)
        assert reject_challenge(chal2, u2, conn=conn) is True

        # 3. Cancel
        chal3 = create_challenge(u1, u2, "DISTANCE", "2026-11-01", "2026-11-08", conn=conn)
        with pytest.raises(PermissionError):
            cancel_challenge(chal3, u2, conn=conn)  # opponent cannot cancel
        assert cancel_challenge(chal3, u1, conn=conn) is True


def test_invitation_expiry():
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "fc_test_exp_1")
        u2 = _create_user(conn, "fc_test_exp_2")

        chal_id = create_challenge(u1, u2, "DISTANCE", "2026-11-01", "2026-11-07", expires_hours=1, conn=conn)
        chal = conn.execute("SELECT * FROM friendly_challenges WHERE id = ?", (chal_id,)).fetchone()

        # Check expiry after 2 hours
        now_dt = datetime.now(timezone.utc) + timedelta(hours=2)
        assert check_and_update_expiry(dict(chal), now_dt=now_dt, conn=conn) is True

        # Opponent cannot accept expired challenge
        with pytest.raises(ValueError, match="(?i)expired"):
            accept_challenge(chal_id, u2, conn=conn)
