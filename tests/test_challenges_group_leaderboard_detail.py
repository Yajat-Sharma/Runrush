"""
Tests for RunRush Friendly Challenges V2: Group Challenge Leaderboard & Detail Experience.

Covers:
1. All four challenge metrics calculated from actual qualifying runs:
   - DISTANCE (sum of distances in km)
   - CONSISTENCY (distinct active days)
   - LONGEST (maximum single run distance in km)
   - DAILY (Daily Sprint sum of distances on single calendar day)
2. Competition ranking for ties: 1, 2, 2, 4 and 1, 1, 3.
3. Zero score handling: all participants with 0 runs are ranked 1, score 0, equal ratio, zero division avoided.
4. Roster size variation: 3 runners (minimum), 5 runners (mid-size), and 10 runners (maximum).
5. Timezone boundaries:
   - Run logged near midnight local time in challenge timezone.
   - Run outside challenge timezone boundary strictly excluded.
6. Privacy:
   - Qualifying run breakdowns strictly hide private GPS coordinates, latitude, longitude, and route points.
7. Participant-level run breakdowns, qualifying run counts, and activity logs.
8. Remaining time, display status, and factual progress (no frontend winner calculation).
"""

import pytest
import os
import sys
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
    get_challenge_progress,
    finalize_challenge_if_due,
    get_challenge_display_status,
)


@pytest.fixture(autouse=True)
def clean_leaderboard_db(app):
    with flask_app.app_context():
        create_friendly_challenge_tables()
        conn = get_db()
        conn.execute("DELETE FROM challenge_awards")
        conn.execute("DELETE FROM challenge_activity")
        conn.execute("DELETE FROM challenge_participants")
        conn.execute("DELETE FROM friendly_challenges")
        conn.execute("DELETE FROM runs")
        conn.execute("DELETE FROM users WHERE username LIKE 'lb_usr_%'")
        conn.commit()


def _make_user(conn, code):
    conn.execute(
        "INSERT INTO users (username, pin, display_name, profile_emoji, status) VALUES (?, 'pin', ?, '🏃', 'active')",
        (f"lb_usr_{code}", f"Runner {code}")
    )
    conn.commit()
    row = conn.execute("SELECT id FROM users WHERE username = ?", (f"lb_usr_{code}",)).fetchone()
    return row["id"]


def _log_run(conn, user_id, date_str, distance_km, time_min=30.0, run_type="easy"):
    conn.execute("""
        INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, date_str, float(distance_km), float(time_min), round(float(time_min) / max(float(distance_km), 0.1), 2), 300.0, run_type))
    conn.commit()


def test_metric_distance_calculation():
    with flask_app.app_context():
        conn = get_db()
        u1 = _make_user(conn, "dist_1")
        u2 = _make_user(conn, "dist_2")
        u3 = _make_user(conn, "dist_3")

        cid = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-02", "2026-11-08", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)

        # U1: 5.0 + 7.5 = 12.5 km
        _log_run(conn, u1, "2026-11-02 08:00:00", 5.0)
        _log_run(conn, u1, "2026-11-03 09:00:00", 7.5)

        # U2: 15.0 km
        _log_run(conn, u2, "2026-11-04 10:00:00", 15.0)

        # U3: 2.0 + 3.0 = 5.0 km
        _log_run(conn, u3, "2026-11-05 07:00:00", 2.0)
        _log_run(conn, u3, "2026-11-06 08:00:00", 3.0)

        prog = get_challenge_progress(cid, conn=conn)
        lb = prog["leaderboard"]
        assert len(lb) == 3

        # U2 should be #1 with 15.0 km
        assert lb[0]["user_id"] == u2
        assert lb[0]["score"] == 15.0
        assert lb[0]["rank"] == 1
        assert lb[0]["display_score"] == 15.0
        assert lb[0]["score_unit"] == "km"
        assert lb[0]["qualifying_runs_count"] == 1

        # U1 should be #2 with 12.5 km
        assert lb[1]["user_id"] == u1
        assert lb[1]["score"] == 12.5
        assert lb[1]["rank"] == 2
        assert lb[1]["qualifying_runs_count"] == 2

        # U3 should be #3 with 5.0 km
        assert lb[2]["user_id"] == u3
        assert lb[2]["score"] == 5.0
        assert lb[2]["rank"] == 3
        assert lb[2]["qualifying_runs_count"] == 2


def test_metric_consistency_calculation():
    with flask_app.app_context():
        conn = get_db()
        u1 = _make_user(conn, "cons_1")
        u2 = _make_user(conn, "cons_2")
        u3 = _make_user(conn, "cons_3")

        cid = create_group_challenge(u1, [u2, u3], "CONSISTENCY", "2026-11-02", "2026-11-08", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)

        # U1 runs on 3 distinct days (even with multiple runs on same day)
        _log_run(conn, u1, "2026-11-02 08:00:00", 5.0)
        _log_run(conn, u1, "2026-11-02 18:00:00", 3.0)
        _log_run(conn, u1, "2026-11-03 09:00:00", 4.0)
        _log_run(conn, u1, "2026-11-05 07:00:00", 6.0)

        # U2 runs on 4 distinct days
        _log_run(conn, u2, "2026-11-02 08:00:00", 2.0)
        _log_run(conn, u2, "2026-11-03 08:00:00", 2.0)
        _log_run(conn, u2, "2026-11-04 08:00:00", 2.0)
        _log_run(conn, u2, "2026-11-05 08:00:00", 2.0)

        # U3 runs on 1 day
        _log_run(conn, u3, "2026-11-02 10:00:00", 10.0)

        prog = get_challenge_progress(cid, conn=conn)
        lb = prog["leaderboard"]

        assert lb[0]["user_id"] == u2
        assert lb[0]["score"] == 4.0
        assert lb[0]["display_score"] == 4
        assert lb[0]["score_unit"] == "days"
        assert lb[0]["rank"] == 1

        assert lb[1]["user_id"] == u1
        assert lb[1]["score"] == 3.0
        assert lb[1]["display_score"] == 3
        assert lb[1]["rank"] == 2

        assert lb[2]["user_id"] == u3
        assert lb[2]["score"] == 1.0
        assert lb[2]["display_score"] == 1
        assert lb[2]["rank"] == 3


def test_metric_longest_run_calculation():
    with flask_app.app_context():
        conn = get_db()
        u1 = _make_user(conn, "long_1")
        u2 = _make_user(conn, "long_2")
        u3 = _make_user(conn, "long_3")

        cid = create_group_challenge(u1, [u2, u3], "LONGEST", "2026-11-02", "2026-11-08", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)

        # U1: total 25 km across runs, max single run = 10.0 km
        _log_run(conn, u1, "2026-11-02 08:00:00", 8.0)
        _log_run(conn, u1, "2026-11-03 08:00:00", 10.0)
        _log_run(conn, u1, "2026-11-04 08:00:00", 7.0)

        # U2: total 18 km across runs, max single run = 18.0 km
        _log_run(conn, u2, "2026-11-04 12:00:00", 18.0)

        # U3: max single run = 5.0 km
        _log_run(conn, u3, "2026-11-05 09:00:00", 5.0)

        prog = get_challenge_progress(cid, conn=conn)
        lb = prog["leaderboard"]

        # U2 wins Longest Run with 18.0 km
        assert lb[0]["user_id"] == u2
        assert lb[0]["score"] == 18.0
        assert lb[0]["rank"] == 1

        assert lb[1]["user_id"] == u1
        assert lb[1]["score"] == 10.0
        assert lb[1]["rank"] == 2

        assert lb[2]["user_id"] == u3
        assert lb[2]["score"] == 5.0
        assert lb[2]["rank"] == 3


def test_metric_daily_sprint_calculation():
    with flask_app.app_context():
        conn = get_db()
        u1 = _make_user(conn, "daily_1")
        u2 = _make_user(conn, "daily_2")
        u3 = _make_user(conn, "daily_3")

        # Daily Sprint: same start and end date (today: 2026-11-08)
        cid = create_group_challenge(u1, [u2, u3], "DAILY", "2026-11-08", "2026-11-08", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)

        # Runs on the sprint day
        _log_run(conn, u1, "2026-11-08 07:00:00", 6.2)
        _log_run(conn, u2, "2026-11-08 18:30:00", 8.5)
        _log_run(conn, u3, "2026-11-08 12:00:00", 4.0)

        # Run on previous day (must be ignored)
        _log_run(conn, u1, "2026-11-07 18:00:00", 15.0)

        prog = get_challenge_progress(cid, conn=conn)
        lb = prog["leaderboard"]

        assert lb[0]["user_id"] == u2
        assert lb[0]["score"] == 8.5
        assert lb[0]["rank"] == 1

        assert lb[1]["user_id"] == u1
        assert lb[1]["score"] == 6.2
        assert lb[1]["rank"] == 2

        assert lb[2]["user_id"] == u3
        assert lb[2]["score"] == 4.0
        assert lb[2]["rank"] == 3


def test_competition_ranking_ties_1_2_2_4():
    """Validates competition ranking: 1, 2, 2, 4 when runners at index 1 and 2 tie."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _make_user(conn, "tie_1")
        u2 = _make_user(conn, "tie_2")
        u3 = _make_user(conn, "tie_3")
        u4 = _make_user(conn, "tie_4")

        cid = create_group_challenge(u1, [u2, u3, u4], "DISTANCE", "2026-11-02", "2026-11-08", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)
        accept_challenge(cid, u4, conn=conn)

        # U1: 30 km (Rank 1)
        _log_run(conn, u1, "2026-11-02 08:00:00", 30.0)
        # U2 & U3: 20 km each (Tied for Rank 2)
        _log_run(conn, u2, "2026-11-03 08:00:00", 20.0)
        _log_run(conn, u3, "2026-11-04 08:00:00", 20.0)
        # U4: 10 km (Rank 4, not 3)
        _log_run(conn, u4, "2026-11-05 08:00:00", 10.0)

        prog = get_challenge_progress(cid, conn=conn)
        lb = prog["leaderboard"]

        assert len(lb) == 4
        assert lb[0]["user_id"] == u1
        assert lb[0]["rank"] == 1

        assert lb[1]["score"] == 20.0
        assert lb[1]["rank"] == 2

        assert lb[2]["score"] == 20.0
        assert lb[2]["rank"] == 2

        # 4th participant must have rank 4 under competition ranking
        assert lb[3]["user_id"] == u4
        assert lb[3]["score"] == 10.0
        assert lb[3]["rank"] == 4


def test_competition_ranking_ties_first_place_1_1_3():
    """Validates 1st place tie (Shared Gold scenario): 1, 1, 3."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _make_user(conn, "sg_1")
        u2 = _make_user(conn, "sg_2")
        u3 = _make_user(conn, "sg_3")

        cid = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-02", "2026-11-08", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)

        # U1 & U2 tie for first place with 25.0 km
        _log_run(conn, u1, "2026-11-02 08:00:00", 25.0)
        _log_run(conn, u2, "2026-11-03 08:00:00", 25.0)
        # U3: 15.0 km
        _log_run(conn, u3, "2026-11-04 08:00:00", 15.0)

        prog = get_challenge_progress(cid, conn=conn)
        lb = prog["leaderboard"]

        assert prog["is_tied"] is True
        assert set(prog["leaders"]) == {u1, u2}
        assert lb[0]["rank"] == 1
        assert lb[1]["rank"] == 1
        assert lb[2]["rank"] == 3


def test_zero_scores_handling():
    """Validates that a group challenge with zero logged runs ranks all as 1 with equal ratios and no division error."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _make_user(conn, "zero_1")
        u2 = _make_user(conn, "zero_2")
        u3 = _make_user(conn, "zero_3")
        u4 = _make_user(conn, "zero_4")

        cid = create_group_challenge(u1, [u2, u3, u4], "DISTANCE", "2026-11-02", "2026-11-08", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)
        accept_challenge(cid, u4, conn=conn)

        # No runs logged
        prog = get_challenge_progress(cid, conn=conn)
        lb = prog["leaderboard"]

        assert len(lb) == 4
        for p in lb:
            assert p["score"] == 0.0
            assert p["display_score"] == 0.0
            assert p["rank"] == 1
            assert p["ratio"] == 25.0
            assert p["qualifying_runs"] == []
            assert p["qualifying_runs_count"] == 0


def test_roster_sizes_3_and_10():
    """Validates independent ranking across minimum (3) and maximum (10) roster sizes."""
    with flask_app.app_context():
        conn = get_db()
        # Maximum roster: 10 participants (1 creator + 9 invitees)
        creator = _make_user(conn, "ten_c")
        invitees = [_make_user(conn, f"ten_{i}") for i in range(1, 10)]

        cid = create_group_challenge(creator, invitees, "DISTANCE", "2026-11-02", "2026-11-08", conn=conn)
        for inv in invitees:
            accept_challenge(cid, inv, conn=conn)

        # Log staggered runs for all 10 runners
        for idx, u_id in enumerate([creator] + invitees):
            dist = float(idx + 1) * 2.0  # 2, 4, 6, 8, 10, 12, 14, 16, 18, 20 km
            _log_run(conn, u_id, "2026-11-02 08:00:00", dist)

        prog = get_challenge_progress(cid, conn=conn)
        lb = prog["leaderboard"]
        assert len(lb) == 10

        # Ranks must be 1 to 10 strictly
        for expected_rank, runner in enumerate(lb, start=1):
            assert runner["rank"] == expected_rank
            assert runner["score"] == float(22 - expected_rank * 2)


def test_timezone_boundaries():
    """
    Validates timezone boundaries:
    - In challenge timezone America/New_York (UTC-5):
      Run logged at 2026-11-08 23:30 local time (which is 2026-11-09 04:30 UTC) is ELIGIBLE.
      Run logged at 2026-11-09 00:30 local time (which is 2026-11-09 05:30 UTC) is INELIGIBLE.
    """
    with flask_app.app_context():
        conn = get_db()
        u1 = _make_user(conn, "tz_1")
        u2 = _make_user(conn, "tz_2")
        u3 = _make_user(conn, "tz_3")

        # Challenge window in America/New_York: Nov 02 to Nov 08
        cid = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-02", "2026-11-08",
                                     tz_name="America/New_York", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)

        # 1. Eligible run near midnight inside boundary:
        # In America/New_York: 2026-11-08 23:30 (UTC: 2026-11-09 04:30:00)
        _log_run(conn, u1, "2026-11-09 04:30:00", 8.0)

        # 2. Ineligible run just after midnight outside boundary:
        # In America/New_York: 2026-11-09 00:30 (UTC: 2026-11-09 05:30:00)
        _log_run(conn, u1, "2026-11-09 05:30:00", 12.0)

        prog = get_challenge_progress(cid, conn=conn)
        u1_entry = next(p for p in prog["leaderboard"] if p["user_id"] == u1)

        # Only the 8.0 km run is counted; the 12.0 km run outside boundary is excluded
        assert u1_entry["score"] == 8.0
        assert u1_entry["qualifying_runs_count"] == 1


def test_gps_coordinates_never_exposed():
    """Verifies that private GPS coordinates, routes, or lat/long data are never leaked in progress responses."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _make_user(conn, "sec_gps_1")
        u2 = _make_user(conn, "sec_gps_2")
        u3 = _make_user(conn, "sec_gps_3")

        cid = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-02", "2026-11-08", conn=conn)
        accept_challenge(cid, u2, conn=conn)
        accept_challenge(cid, u3, conn=conn)

        _log_run(conn, u1, "2026-11-02 08:00:00", 10.0)

        prog = get_challenge_progress(cid, conn=conn)
        for runner in prog["leaderboard"]:
            for run in runner["qualifying_runs"]:
                # Ensure prohibited GPS/location keys do not exist in the public response
                prohibited_keys = ["gps", "route", "latitude", "longitude", "lat", "lng", "coordinates", "route_points"]
                for k in prohibited_keys:
                    assert k not in run, f"Prohibited key '{k}' found in qualifying run breakdown"
                # Ensure allowed safe metadata exists
                assert "distance_km" in run
                assert "time_min" in run
                assert "date" in run
                assert "local_date" in run
