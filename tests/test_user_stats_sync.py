"""
user_stats is a denormalized cache (total distance + streaks) kept in sync by
the run write paths. edit_run and clear_data used to skip it, so the cached
total (read by the leaderboard and distance badges) drifted from the runs
table, and because add_run only increments it the drift was never repaired.

These tests pin the cache to the runs table after every write path, and cover
the repair command for rows that already drifted.
"""

from datetime import date, timedelta

import pytest
from db import get_db


def register_and_login(client, username='alice', pin='1234'):
    client.post('/register', data={'username': username, 'pin': pin})
    client.post('/login', data={'username': username, 'pin': pin})


def uid(username='alice'):
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row['id']


def stats(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM user_stats WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row


def runs_total(user_id):
    conn = get_db()
    row = conn.execute("SELECT COALESCE(SUM(distance_km), 0) AS t FROM runs WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row['t']


def add_run(client, distance, time_min, on=None):
    r = client.post('/add', data={
        'date': (on or date.today()).isoformat(),
        'distance': str(distance), 'time': str(time_min), 'run_type': 'easy',
    })
    assert r.status_code in (200, 302)


def latest_run_id(user_id):
    conn = get_db()
    row = conn.execute("SELECT id FROM runs WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    conn.close()
    return row['id']


def edit_run(client, run_id, distance, time_min, on):
    r = client.post(f'/edit/{run_id}', data={
        'date': on.isoformat(), 'distance': str(distance), 'time': str(time_min),
    })
    assert r.status_code in (200, 302)


class TestWritePathsKeepStatsInSync:

    def test_add_and_delete_still_in_sync(self, client):
        register_and_login(client)
        add_run(client, 5.0, 30)
        add_run(client, 3.0, 20, date.today() - timedelta(days=3))
        assert stats(uid())['total_distance_km'] == pytest.approx(8.0)
        client.post(f'/delete/{latest_run_id(uid())}')
        assert stats(uid())['total_distance_km'] == pytest.approx(runs_total(uid()))

    def test_editing_distance_updates_total(self, client):
        register_and_login(client)
        add_run(client, 5.0, 30)
        edit_run(client, latest_run_id(uid()), 8.0, 48, date.today())
        assert stats(uid())['total_distance_km'] == pytest.approx(8.0)

    def test_editing_date_updates_streaks(self, client):
        register_and_login(client)
        add_run(client, 5.0, 30)                                  # today
        add_run(client, 4.0, 25, date.today() - timedelta(days=5))
        assert stats(uid())['current_streak'] == 1
        # move the old run to yesterday -> today + yesterday = 2-day streak
        edit_run(client, latest_run_id(uid()), 4.0, 25, date.today() - timedelta(days=1))
        s = stats(uid())
        assert s['current_streak'] == 2
        assert s['best_streak'] == 2

    def test_clearing_all_runs_resets_stats(self, client):
        register_and_login(client)
        add_run(client, 5.0, 30)
        assert stats(uid())['total_distance_km'] == pytest.approx(5.0)
        client.post('/settings/clear-data')
        s = stats(uid())
        assert s['total_distance_km'] == 0
        assert s['current_streak'] == 0
        assert s['best_streak'] == 0

    def test_add_after_edit_does_not_carry_drift_forward(self, client):
        """add_run is incremental, so a stale base used to persist forever."""
        register_and_login(client)
        add_run(client, 5.0, 30)
        edit_run(client, latest_run_id(uid()), 9.0, 54, date.today())
        add_run(client, 1.0, 6, date.today() - timedelta(days=2))
        assert stats(uid())['total_distance_km'] == pytest.approx(10.0)


class TestRecalculateHelper:

    def test_repairs_stale_total_and_streaks(self, client):
        register_and_login(client)
        add_run(client, 5.0, 30)
        conn = get_db()
        conn.execute("UPDATE user_stats SET total_distance_km = 99, current_streak = 7, best_streak = 7 WHERE user_id = ?", (uid(),))
        conn.commit()
        conn.close()

        from app import recalculate_user_stats
        recalculate_user_stats(uid())
        s = stats(uid())
        assert s['total_distance_km'] == pytest.approx(5.0)
        assert s['current_streak'] == 1
        assert s['best_streak'] == 1
        assert s['last_activity_date'] == date.today().isoformat()

    def test_creates_missing_row_and_is_idempotent(self, client):
        register_and_login(client)
        conn = get_db()
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type) VALUES (?, ?, 4.0, 24, 6.0, 250, 'easy')",
            (uid(), date.today().isoformat()))
        conn.execute("DELETE FROM user_stats WHERE user_id = ?", (uid(),))
        conn.commit()
        conn.close()
        assert stats(uid()) is None

        from app import recalculate_user_stats
        recalculate_user_stats(uid())
        recalculate_user_stats(uid())
        assert stats(uid())['total_distance_km'] == pytest.approx(4.0)

    def test_user_with_no_runs_gets_zeroes(self, client):
        register_and_login(client)
        from app import recalculate_user_stats
        recalculate_user_stats(uid())
        s = stats(uid())
        assert (s['total_distance_km'], s['current_streak'], s['best_streak']) == (0, 0, 0)
        assert s['last_activity_date'] is None


class TestResyncCommand:

    def _drift(self, client):
        register_and_login(client)
        add_run(client, 5.0, 30)
        conn = get_db()
        conn.execute("UPDATE user_stats SET total_distance_km = 42 WHERE user_id = ?", (uid(),))
        conn.commit()
        conn.close()

    def test_default_run_reports_drift_but_writes_nothing(self, client, runner):
        self._drift(client)
        res = runner.invoke(args=['resync-user-stats'])
        assert res.exit_code == 0, res.output
        assert 'alice' in res.output
        assert stats(uid())['total_distance_km'] == 42

    def test_apply_repairs_and_second_run_finds_nothing(self, client, runner):
        self._drift(client)
        res = runner.invoke(args=['resync-user-stats', '--apply'])
        assert res.exit_code == 0, res.output
        assert stats(uid())['total_distance_km'] == pytest.approx(5.0)
        again = runner.invoke(args=['resync-user-stats'])
        assert 'alice' not in again.output
        assert '0 user' in again.output
