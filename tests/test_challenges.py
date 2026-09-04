import pytest
import os
import sys
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["DATABASE_URL"] = "sqlite:///test_runs.db"
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci")
os.environ.setdefault("GOOGLE_CLIENT_ID", "mock-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "mock-client-secret")

from app import app as flask_app, init_db
from db import get_db
from services.challenge_service import (
    CHALLENGES, get_active_challenges, evaluate_challenges_for_user,
    get_user_challenges, reset_challenge_progress,
)
from services.badge_service import get_user_badges


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _this_month():
    today = date.today()
    return today.strftime("%Y-%m-%d")


def _create_user(conn, username="ch_test"):
    conn.execute(
        "INSERT INTO users (username, pin) VALUES (?, ?)",
        (username, "dummy_hash"),
    )
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    return row["id"]


def _add_run(conn, user_id, distance_km, date_str=None):
    if date_str is None:
        date_str = _this_month()
    pace = 5.0
    conn.execute(
        "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, date_str, distance_km, distance_km * pace, pace, distance_km * 60),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM runs WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)
    ).fetchone()
    return row["id"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fresh_db(app):
    # 'app' fixture from conftest.py already sets up the in-memory DB and keeps it alive.
    # We just need to depend on it.
    yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestChallengesActive:
    def test_active_challenges_returned_this_month(self):
        active = get_active_challenges()
        assert len(active) > 0, "Should have active challenges this month"

    def test_challenge_outside_date_range_not_returned(self, monkeypatch):
        import services.challenge_service as cs
        old_build = cs._build_challenges

        def expired_challenges():
            return [
                {
                    "key": "EXPIRED",
                    "name": "Expired",
                    "description": "Old challenge",
                    "goal_type": "distance_km",
                    "goal_value": 1.0,
                    "start_date": "2020-01-01",
                    "end_date": "2020-01-31",
                    "reward_badge_key": "TOTAL_50KM",
                    "icon": "fas fa-running",
                }
            ]

        monkeypatch.setattr(cs, "CHALLENGES", expired_challenges())
        active = cs.get_active_challenges()
        assert len(active) == 0, "Expired challenge should not appear in active list"


class TestChallengeProgressOnAdd:
    def test_adding_run_updates_distance_progress(self):
        with flask_app.app_context():
            conn = get_db()
            user_id = _create_user(conn)
            run_id = _add_run(conn, user_id, distance_km=10.0)
            conn.close()
            evaluate_challenges_for_user(user_id, run_id)
            challenges = get_user_challenges(user_id)
            km20 = next(c for c in challenges if c["key"] == "MONTHLY_20KM")
            assert km20["current_progress"] == pytest.approx(10.0, abs=0.1)
            assert km20["percent_complete"] == 50

    def test_run_count_progress(self):
        with flask_app.app_context():
            conn = get_db()
            user_id = _create_user(conn, "count_user")
            for _ in range(3):
                r_id = _add_run(conn, user_id, distance_km=3.0)
            conn.close()
            evaluate_challenges_for_user(user_id)
            challenges = get_user_challenges(user_id)
            run10 = next(c for c in challenges if c["key"] == "MONTHLY_10RUNS")
            assert run10["current_progress"] == pytest.approx(3.0, abs=0.1)
            assert run10["percent_complete"] == 30

    def test_single_long_run_progress(self):
        with flask_app.app_context():
            conn = get_db()
            user_id = _create_user(conn, "long_user")
            run_id = _add_run(conn, user_id, distance_km=16.0)
            conn.close()
            evaluate_challenges_for_user(user_id, run_id)
            challenges = get_user_challenges(user_id)
            long_run = next(c for c in challenges if c["key"] == "MONTHLY_LONG_RUN")
            assert long_run["completed"] is True
            assert long_run["percent_complete"] == 100


class TestChallengeCompletion:
    def test_reaching_goal_marks_completed_and_awards_badge(self):
        with flask_app.app_context():
            conn = get_db()
            user_id = _create_user(conn, "complete_user")
            # MONTHLY_20KM needs 20km
            _add_run(conn, user_id, distance_km=12.0)
            _add_run(conn, user_id, distance_km=9.0)
            conn.close()
            evaluate_challenges_for_user(user_id)
            challenges = get_user_challenges(user_id)
            km20 = next(c for c in challenges if c["key"] == "MONTHLY_20KM")
            assert km20["completed"] is True, "Challenge should be marked complete"
            assert km20["completed_at"] is not None
            # Check reward badge was awarded
            badges = get_user_badges(user_id)
            badge_keys = [b["badge_key"] for b in badges]
            assert "TOTAL_50KM" in badge_keys, "Reward badge TOTAL_50KM should have been awarded"

    def test_already_completed_challenge_not_awarded_twice(self):
        with flask_app.app_context():
            conn = get_db()
            user_id = _create_user(conn, "dupe_user")
            _add_run(conn, user_id, distance_km=21.0)
            conn.close()
            evaluate_challenges_for_user(user_id)
            evaluate_challenges_for_user(user_id)  # Second call
            badges = get_user_badges(user_id)
            awarded = [b["badge_key"] for b in badges if b["badge_key"] == "TOTAL_50KM"]
            assert len(awarded) == 1, "Badge should be awarded exactly once"


class TestZeroProgressAccount:
    def test_fresh_account_returns_zero_progress(self):
        with flask_app.app_context():
            conn = get_db()
            user_id = _create_user(conn, "zero_user")
            conn.close()
            challenges = get_user_challenges(user_id)
            assert len(challenges) > 0
            for c in challenges:
                assert c["current_progress"] == 0.0
                assert c["completed"] is False
                assert c["percent_complete"] == 0


class TestProgressOnEdit:
    def test_editing_run_distance_down_recalculates_progress(self):
        with flask_app.app_context():
            conn = get_db()
            user_id = _create_user(conn, "edit_user")
            run_id = _add_run(conn, user_id, distance_km=10.0)
            conn.close()
            evaluate_challenges_for_user(user_id, run_id)
            challenges_before = get_user_challenges(user_id)
            km20_before = next(c for c in challenges_before if c["key"] == "MONTHLY_20KM")
            assert km20_before["current_progress"] == pytest.approx(10.0, abs=0.1)

            # Edit run down to 2km
            with flask_app.app_context():
                conn = get_db()
                conn.execute(
                    "UPDATE runs SET distance_km = 2.0, time_min = 10.0, pace = 5.0 WHERE id = ?",
                    (run_id,),
                )
                conn.commit()
                conn.close()
                evaluate_challenges_for_user(user_id, run_id)

            challenges_after = get_user_challenges(user_id)
            km20_after = next(c for c in challenges_after if c["key"] == "MONTHLY_20KM")
            assert km20_after["current_progress"] == pytest.approx(2.0, abs=0.1), \
                "Progress should drop after editing run distance down"

    def test_editing_run_distance_up_triggers_badge_and_challenge(self):
        with flask_app.app_context():
            conn = get_db()
            user_id = _create_user(conn, "edit_up_user")
            run_id = _add_run(conn, user_id, distance_km=2.0)
            conn.close()
            evaluate_challenges_for_user(user_id, run_id)
            badges_before = [b["badge_key"] for b in get_user_badges(user_id)]
            assert "FIRST_5K" not in badges_before

            # Edit run up to 5.2km (should trigger FIRST_5K badge)
            with flask_app.app_context():
                conn = get_db()
                conn.execute(
                    "UPDATE runs SET distance_km = 5.2, time_min = 26.0, pace = 5.0 WHERE id = ?",
                    (run_id,),
                )
                conn.commit()
                conn.close()
                from services.badge_service import evaluate_badges_for_user
                evaluate_badges_for_user(user_id, run_id)
                evaluate_challenges_for_user(user_id, run_id)

            badges_after = [b["badge_key"] for b in get_user_badges(user_id)]
            assert "FIRST_5K" in badges_after, "FIRST_5K badge should be earned after editing distance to 5.2km"
            challenges_after = get_user_challenges(user_id)
            km20_after = next(c for c in challenges_after if c["key"] == "MONTHLY_20KM")
            assert km20_after["current_progress"] == pytest.approx(5.2, abs=0.1), \
                "Challenge progress should reflect edited distance"


class TestProgressOnDelete:
    def test_deleting_run_recalculates_progress(self):
        with flask_app.app_context():
            conn = get_db()
            user_id = _create_user(conn, "del_user")
            run_id1 = _add_run(conn, user_id, distance_km=8.0)
            run_id2 = _add_run(conn, user_id, distance_km=7.0)
            conn.close()
            evaluate_challenges_for_user(user_id)
            challenges_before = get_user_challenges(user_id)
            km20_before = next(c for c in challenges_before if c["key"] == "MONTHLY_20KM")
            assert km20_before["current_progress"] == pytest.approx(15.0, abs=0.1)

            # Delete one run
            with flask_app.app_context():
                conn = get_db()
                conn.execute("DELETE FROM runs WHERE id = ?", (run_id2,))
                conn.commit()
                conn.close()
                evaluate_challenges_for_user(user_id)

            challenges_after = get_user_challenges(user_id)
            km20_after = next(c for c in challenges_after if c["key"] == "MONTHLY_20KM")
            assert km20_after["current_progress"] == pytest.approx(8.0, abs=0.1), \
                "Progress should drop after run is deleted"


class TestChallengesAPI:
    def test_api_challenges_requires_login(self):
        flask_app.config["TESTING"] = True
        flask_app.config["RATELIMIT_ENABLED"] = False
        with flask_app.test_client() as c:
            resp = c.get("/api/challenges")
            assert resp.status_code == 401

    def test_api_challenges_returns_list(self):
        flask_app.config["TESTING"] = True
        flask_app.config["WTF_CSRF_ENABLED"] = False
        with flask_app.app_context():
            init_db()
        with flask_app.test_client() as c:
            c.post("/register", data={"username": "api_ch_user", "pin": "1234"})
            c.post("/login", data={"username": "api_ch_user", "pin": "1234"})
            resp = c.get("/api/challenges")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "success"
            assert isinstance(data["challenges"], list)
            assert len(data["challenges"]) > 0
