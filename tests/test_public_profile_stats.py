"""
Regression tests for Public Profile data bugs found in the final audit.

Bug 1 -- Total Distance showed 0 while Longest Run was correct.
  /api/user/<username>/public-profile read total_distance_km from the
  denormalized user_stats cache but run_count / total_time / longest_run from
  the runs table itself (and avg pace mixed both). user_stats is only kept in
  sync by some write paths: edit_run and clear_data never touch it, and rows
  inserted outside the app's add paths never create it. The profile therefore
  showed a stale or zero total next to correct sibling stats.

Bug 2 -- Pace Pet names rendered as "undefined" (see test_profile_pet_render.py
  for the frontend half; the API-contract half is here).
"""

from datetime import date

import pytest
from db import get_db


def register_and_login(client, username='alice', pin='1234'):
    client.post('/register', data={'username': username, 'pin': pin})
    client.post('/login', data={'username': username, 'pin': pin})


def user_id(username):
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row['id']


def insert_run_out_of_band(uid, distance, time_min, run_date=None):
    """Insert straight into runs, bypassing the app's add path (and user_stats)."""
    conn = get_db()
    conn.execute(
        "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type) "
        "VALUES (?, ?, ?, ?, ?, ?, 'easy')",
        (uid, run_date or date.today().isoformat(), distance, time_min,
         round(time_min / distance, 2), 300),
    )
    conn.commit()
    conn.close()


def add_run_via_app(client, distance, time_min):
    r = client.post('/add', data={
        'date': date.today().isoformat(),
        'distance': str(distance),
        'time': str(time_min),
        'run_type': 'easy',
    })
    assert r.status_code in (200, 302), r.status_code


def latest_run_id(uid):
    conn = get_db()
    row = conn.execute("SELECT id FROM runs WHERE user_id = ? ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
    conn.close()
    return row['id']


def profile(client, username):
    res = client.get(f'/api/user/{username}/public-profile')
    assert res.status_code == 200, res.status_code
    return res.get_json()


class TestTotalDistance:

    def test_total_distance_after_normal_add(self, client):
        """Baseline: the app's own add path already worked."""
        register_and_login(client)
        add_run_via_app(client, 6.2, 34)
        d = profile(client, 'alice')
        assert d['total_distance_km'] == 6.2
        assert d['longest_run_km'] == 6.2
        assert d['run_count'] == 1

    def test_total_distance_matches_runs_when_user_stats_missing(self, client):
        """The reproduced symptom: runs exist, longest run correct, total 0."""
        register_and_login(client)
        uid = user_id('alice')
        insert_run_out_of_band(uid, 5.0, 30)
        insert_run_out_of_band(uid, 7.5, 45)
        d = profile(client, 'alice')
        assert d['longest_run_km'] == 7.5
        assert d['run_count'] == 2
        assert d['total_distance_km'] == 12.5
        # avg pace derives from total time / total distance, so it must be real too
        assert d['avg_pace_min_per_km'] == round(75 / 12.5, 2)

    def test_total_distance_after_editing_a_run(self, client):
        """edit_run changes runs.distance_km but never updates user_stats."""
        register_and_login(client)
        add_run_via_app(client, 5.0, 30)
        rid = latest_run_id(user_id('alice'))
        r = client.post(f'/edit/{rid}', data={
            'date': date.today().isoformat(), 'distance': '8.0', 'time': '48',
        })
        assert r.status_code in (200, 302)
        d = profile(client, 'alice')
        assert d['longest_run_km'] == 8.0
        assert d['total_distance_km'] == 8.0

    def test_total_distance_after_clearing_all_runs(self, client):
        """clear_data deletes every run but never resets user_stats."""
        register_and_login(client)
        add_run_via_app(client, 5.0, 30)
        assert profile(client, 'alice')['total_distance_km'] == 5.0
        r = client.post('/settings/clear-data')
        assert r.status_code in (200, 302)
        d = profile(client, 'alice')
        assert d['run_count'] == 0
        assert d['total_distance_km'] == 0

    def test_username_lookup_remains_case_insensitive(self, client):
        register_and_login(client)
        insert_run_out_of_band(user_id('alice'), 4.0, 24)
        d = profile(client, 'ALICE')
        assert d['username'] == 'alice'
        assert d['total_distance_km'] == 4.0


class TestPetCollectionContract:
    """Documents the API shape the profile frontend must respect."""

    def test_unowned_pets_are_catalog_entries_without_a_name(self, client):
        register_and_login(client)
        res = client.get('/api/pet-collection?username=alice')
        assert res.status_code == 200
        collection = res.get_json()['collection']
        # The catalog is never empty -- one entry per pet type -- so a
        # frontend length check alone can never detect "no pets".
        assert len(collection) > 0
        for entry in collection:
            assert entry['status'] in ('owned', 'unlocked', 'locked')
            if entry['status'] != 'owned':
                assert 'pet_name' not in entry
                assert 'level' not in entry
                assert 'level_name' not in entry
