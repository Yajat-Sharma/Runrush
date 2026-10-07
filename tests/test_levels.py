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
        assert mins[0] == 0
        assert mins == sorted(set(mins))
        assert [e["level"] for e in ladder()] == list(range(1, 11))

    def test_boundaries(self):
        assert level_for_km(0)["level"] == 1
        assert level_for_km(24.99)["level"] == 1
        assert level_for_km(25)["level"] == 2
        assert level_for_km(149.9)["level"] == 3
        assert level_for_km(150)["level"] == 4
        assert level_for_km(100000)["level"] == 10

    def test_bad_input_is_level_one(self):
        assert level_for_km(None)["level"] == 1
        assert level_for_km(-5)["level"] == 1

    def test_progress_and_km_to_next(self):
        info = level_info(50)  # halfway between Jogger (25) and Strider (75)
        assert info["level"] == 2
        assert info["progress"] == 0.5
        assert info["km_to_next"] == 25.0
        assert info["next"]["title"] == "Strider"
        assert not info["is_max"]

    def test_max_level_has_no_next(self):
        info = level_info(5000)
        assert info["is_max"] and info["next"] is None and info["progress"] == 1.0

    def test_detect_level_up(self):
        assert detect_level_up(20, 26)["level"] == 2
        assert detect_level_up(26, 30) is None
        assert detect_level_up(20, 200)["level"] == 4   # skipped levels -> highest reached
        assert detect_level_up(30, 20) is None          # never "levels up" backwards


# --- API / feed / celebration ---

class TestLevelEndpoints:

    def test_level_requires_login(self, client):
        assert client.get('/api/level').status_code == 401

    def test_level_for_new_runner(self, client):
        login_as(client, 'lv_new')
        d = client.get('/api/level').get_json()
        assert d["level"] == 1 and d["title"] == "Couch Starter"
        assert len(d["ladder"]) == 10

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
        assert b'showLevelUp({' not in client.get('/dashboard').data

    def test_level_up_sends_notification(self, client):
        login_as(client, 'lv_notif')
        log_run(client, 30, 180)
        titles = [n["title"] for n in client.get('/api/notifications').get_json()["notifications"]]
        assert any("Jogger" in t for t in titles)
