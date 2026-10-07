"""
Tests for the distance-only rank ladder: level maths, the /api/level endpoint,
rank chips in the runners feed, and the level-up celebration.
"""

from datetime import date

from services.level_service import (
    LEVELS, detect_level_up, ladder, level_for_km, level_info,
)


def login_as(client, username, pin='1234'):
    client.get('/logout')
    client.post('/register', data={'username': username, 'pin': pin})
    client.post('/login', data={'username': username, 'pin': pin})


def log_run(client, distance, time_min):
    r = client.post('/add', data={
        'date': date.today().isoformat(),
        'distance': str(distance),
        'time': str(time_min),
        'run_type': 'easy',
    })
    assert r.status_code in (200, 302), r.status_code


# --- Pure level maths ---

class TestLevelMaths:

    def test_ladder_has_ten_ascending_levels(self):
        mins = [lv[4] for lv in LEVELS]
        assert len(LEVELS) == 10
        assert mins[0] == 1  # Couch Starter is earned at the first km
        assert mins == sorted(set(mins))
        assert [e["level"] for e in ladder()] == list(range(1, 11))

    def test_boundaries(self):
        assert level_for_km(0) is None
        assert level_for_km(0.99) is None
        assert level_for_km(1)["level"] == 1
        assert level_for_km(24.99)["level"] == 1
        assert level_for_km(25)["level"] == 2
        assert level_for_km(149.9)["level"] == 3
        assert level_for_km(150)["level"] == 4
        assert level_for_km(100000)["level"] == 10

    def test_bad_input_is_unranked(self):
        assert level_for_km(None) is None
        assert level_for_km(-5) is None

    def test_progress_and_km_to_next(self):
        info = level_info(50)  # halfway between Jogger (25) and Strider (75)
        assert info["level"] == 2
        assert info["progress"] == 0.5
        assert info["km_to_next"] == 25.0
        assert info["next"]["title"] == "Strider"
        assert not info["is_max"]

    def test_unranked_info_points_at_first_rank(self):
        info = level_info(0.4)
        assert info["unranked"] and info["level"] == 0
        assert info["next"]["title"] == "Couch Starter"
        assert info["km_to_next"] == 0.6
        assert not level_info(1)["unranked"]

    def test_max_level_has_no_next(self):
        info = level_info(5000)
        assert info["is_max"] and info["next"] is None and info["progress"] == 1.0

    def test_detect_level_up(self):
        assert detect_level_up(20, 26)["level"] == 2
        assert detect_level_up(26, 30) is None
        assert detect_level_up(20, 200)["level"] == 4   # skipped levels -> highest reached
        assert detect_level_up(30, 20) is None          # never "levels up" backwards
        assert detect_level_up(0, 0.5) is None          # still unranked
        assert detect_level_up(0, 1.2)["level"] == 1    # first rank earned at 1 km


# --- API / feed / celebration ---

class TestLevelEndpoints:

    def test_level_requires_login(self, client):
        assert client.get('/api/level').status_code == 401

    def test_new_runner_is_unranked_until_first_km(self, client):
        login_as(client, 'lv_new')
        d = client.get('/api/level').get_json()
        assert d["unranked"] and d["level"] == 0
        assert d["next"]["title"] == "Couch Starter"
        assert len(d["ladder"]) == 10
        log_run(client, 0.5, 5)
        assert client.get('/api/level').get_json()["unranked"]
        log_run(client, 0.6, 6)  # 1.1 km total
        d = client.get('/api/level').get_json()
        assert not d["unranked"] and d["title"] == "Couch Starter"

    def test_unranked_runner_has_no_feed_chip(self, client):
        login_as(client, 'lv_nochip')
        log_run(client, 0.5, 5)
        run = client.get('/api/feed').get_json()["runs"][0]
        assert run["rank"] is None

    def test_level_reflects_distance(self, client):
        login_as(client, 'lv_dist')
        log_run(client, 10, 60)
        d = client.get('/api/level').get_json()
        assert d["total_km"] == 10.0
        assert d["km_to_next"] == 15.0

    def test_feed_runs_carry_rank(self, client):
        login_as(client, 'lv_feed')
        log_run(client, 5, 30)
        run = client.get('/api/feed').get_json()["runs"][0]
        assert run["rank"]["level"] == 1
        assert {"title", "icon", "color"} <= set(run["rank"])

    def test_crossing_a_level_queues_celebration_once(self, client):
        login_as(client, 'lv_up')
        log_run(client, 30, 180)  # 30 km total -> Jogger
        page = client.get('/dashboard')
        assert b'showLevelUp({' in page.data
        assert b'Jogger' in page.data
        # shown once, then cleared
        assert b'showLevelUp({' not in client.get('/dashboard').data

    def test_staying_in_a_level_does_not_celebrate(self, client):
        login_as(client, 'lv_stay')
        log_run(client, 5, 30)
        # the first run earns Couch Starter, so it celebrates once
        assert b'showLevelUp({' in client.get('/dashboard').data
        log_run(client, 5, 30)  # 10 km total, still Couch Starter
        assert b'showLevelUp({' not in client.get('/dashboard').data

    def test_level_up_sends_notification(self, client):
        login_as(client, 'lv_notif')
        log_run(client, 30, 180)
        titles = [n["title"] for n in client.get('/api/notifications').get_json()["notifications"]]
        assert any("Jogger" in t for t in titles)


# --- Rank on leaderboards, profiles and people lists ---

class TestRankEverywhere:

    def test_profile_api_includes_rank(self, client):
        login_as(client, 'rk_prof')
        log_run(client, 30, 180)
        d = client.get('/api/user/rk_prof/public-profile').get_json()
        assert d["rank"]["title"] == "Jogger"
        assert d["rank"]["level"] == 2
        assert {"icon", "color", "km_to_next"} <= set(d["rank"])

    def test_leaderboard_shows_rank_chips(self, client):
        login_as(client, 'rk_lb')
        log_run(client, 30, 180)
        page = client.get('/dashboard').data
        assert b'rk-chip' in page and b'Jogger' in page

    def test_follow_and_suggestion_lists_carry_rank(self, client):
        login_as(client, 'rk_a')
        log_run(client, 5, 30)
        login_as(client, 'rk_b')
        people = client.get('/api/social/runners').get_json()['runners']
        assert people and all(p["rank"]["title"] for p in people)
