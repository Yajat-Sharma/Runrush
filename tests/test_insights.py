"""
Tests for the /api/analytics/insights endpoint.

Each test seeds a KNOWN set of runs with specific dates, distances, and paces,
then asserts the insight calculations produce EXACT expected values.
"""

import pytest
from datetime import datetime, timedelta, date
from unittest.mock import patch

from app import app as flask_app
from db import get_db


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """Create an authenticated test client with a fresh user."""
    client.post('/register', data={'username': 'insight_tester', 'pin': '1234'})
    client.post('/login', data={'username': 'insight_tester', 'pin': '1234'})
    return client


def _get_user_id(app):
    """Get the test user's ID."""
    with app.app_context():
        conn = get_db()
        user = conn.execute("SELECT id FROM users WHERE username = 'insight_tester'").fetchone()
        conn.close()
        return user['id']


def _seed_runs(app, runs_data):
    """
    Seed runs into the database.
    runs_data: list of (date_str, distance_km, pace, time_min)
    """
    user_id = _get_user_id(app)
    with app.app_context():
        conn = get_db()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for date_str, distance_km, pace, time_min in runs_data:
            conn.execute(
                "INSERT INTO runs (user_id, date, distance_km, pace, time_min, calories, run_type, notes, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, date_str, distance_km, pace, time_min, 0, 'easy', '', now_str)
            )
        conn.commit()
        conn.close()


# ───────────────────────────────────────────────────────
# TEST 1: No runs → no insights returned
# ───────────────────────────────────────────────────────
def test_no_runs_returns_empty(app, auth_client):
    """With zero runs, the endpoint should return an empty insights list."""
    resp = auth_client.get('/api/analytics/insights')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['insights'] == []


# ───────────────────────────────────────────────────────
# TEST 2: Getting Faster — exact percentage calculation
# ───────────────────────────────────────────────────────
def test_getting_faster_exact_calculation(app, auth_client):
    """
    FIXTURE DATA:
      Previous month: 2 runs with paces 7.0 and 6.0 → avg = 6.5 min/km
      Current month:  2 runs with paces 6.0 and 5.0 → avg = 5.5 min/km

    EXPECTED:
      pace_change_pct = ((6.5 - 5.5) / 6.5) * 100 = 15.384...% → "15.4%"
    """
    today = date.today()
    curr_month_start = today.replace(day=1)
    prev_month_end = curr_month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)

    runs = [
        # Previous month: 2 runs
        (prev_month_start.strftime("%Y-%m-%d"), 5.0, 7.0, 35.0),
        ((prev_month_start + timedelta(days=5)).strftime("%Y-%m-%d"), 5.0, 6.0, 30.0),
        # Current month: 2 runs
        (curr_month_start.strftime("%Y-%m-%d"), 5.0, 6.0, 30.0),
        ((curr_month_start + timedelta(days=3)).strftime("%Y-%m-%d"), 5.0, 5.0, 25.0),
    ]
    _seed_runs(app, runs)

    resp = auth_client.get('/api/analytics/insights')
    data = resp.get_json()

    pace_insight = next((i for i in data['insights'] if i['title'] == 'Getting Faster'), None)
    assert pace_insight is not None, f"Expected 'Getting Faster' insight, got: {[i['title'] for i in data['insights']]}"
    assert "15.4%" in pace_insight['description'], \
        f"Expected 15.4% improvement, got: {pace_insight['description']}"


# ───────────────────────────────────────────────────────
# TEST 3: Distance Growth — exact km calculation
# ───────────────────────────────────────────────────────
def test_distance_growth_exact_calculation(app, auth_client):
    """
    FIXTURE DATA:
      Previous month: 2 runs of 5.0 km each → total = 10.0 km
      Current month:  2 runs of 8.0 km each → total = 16.0 km

    EXPECTED:
      delta_km = 16.0 - 10.0 = 6.0 km → "6.0 km more"
    """
    today = date.today()
    curr_month_start = today.replace(day=1)
    prev_month_end = curr_month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)

    runs = [
        # Previous month: 2 runs of 5km
        (prev_month_start.strftime("%Y-%m-%d"), 5.0, 6.0, 30.0),
        ((prev_month_start + timedelta(days=3)).strftime("%Y-%m-%d"), 5.0, 6.0, 30.0),
        # Current month: 2 runs of 8km
        (curr_month_start.strftime("%Y-%m-%d"), 8.0, 6.0, 48.0),
        ((curr_month_start + timedelta(days=3)).strftime("%Y-%m-%d"), 8.0, 6.0, 48.0),
    ]
    _seed_runs(app, runs)

    resp = auth_client.get('/api/analytics/insights')
    data = resp.get_json()

    dist_insight = next((i for i in data['insights'] if i['title'] == 'Distance Growth'), None)
    assert dist_insight is not None, f"Expected 'Distance Growth' insight, got: {[i['title'] for i in data['insights']]}"
    assert "6.0 km more" in dist_insight['description'], \
        f"Expected 6.0 km more, got: {dist_insight['description']}"


# ───────────────────────────────────────────────────────
# TEST 4: Threshold enforcement — <2 runs suppresses comparison insights
# ───────────────────────────────────────────────────────
def test_insufficient_data_suppresses_comparison_insights(app, auth_client):
    """
    Only 1 run in current month and 1 in previous month.
    'Getting Faster' and 'Distance Growth' should NOT appear (threshold = 2 in both).
    'Consistency', 'Typical Run', and 'Best Performance' SHOULD still appear.
    """
    today = date.today()
    curr_month_start = today.replace(day=1)
    prev_month_end = curr_month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)

    runs = [
        (prev_month_start.strftime("%Y-%m-%d"), 5.0, 6.0, 30.0),  # 1 run prev
        (curr_month_start.strftime("%Y-%m-%d"), 5.0, 6.0, 30.0),  # 1 run curr
    ]
    _seed_runs(app, runs)

    resp = auth_client.get('/api/analytics/insights')
    data = resp.get_json()
    titles = [i['title'] for i in data['insights']]

    assert 'Getting Faster' not in titles, f"Getting Faster should be suppressed with <2 runs, but got: {titles}"
    assert 'Distance Growth' not in titles, f"Distance Growth should be suppressed with <2 runs, but got: {titles}"
    assert 'Consistency' in titles
    assert 'Your Typical Run' in titles
    assert 'Best Performance' in titles


# ───────────────────────────────────────────────────────
# TEST 5: Favorite Running Day — threshold enforcement
# ───────────────────────────────────────────────────────
def test_favorite_day_requires_5_runs(app, auth_client):
    """
    With only 4 total runs, 'Favorite Running Day' should NOT appear.
    With 5+ runs, it SHOULD appear.
    """
    today = date.today()

    # Seed 4 runs (below threshold)
    runs = [
        ((today - timedelta(days=i)).strftime("%Y-%m-%d"), 5.0, 6.0, 30.0)
        for i in range(4)
    ]
    _seed_runs(app, runs)

    resp = auth_client.get('/api/analytics/insights')
    data = resp.get_json()
    titles = [i['title'] for i in data['insights']]
    assert 'Favorite Running Day' not in titles, \
        f"Favorite Running Day should be suppressed with 4 runs, but got: {titles}"

    # Add a 5th run to cross the threshold
    _seed_runs(app, [((today - timedelta(days=10)).strftime("%Y-%m-%d"), 5.0, 6.0, 30.0)])

    resp = auth_client.get('/api/analytics/insights')
    data = resp.get_json()
    titles = [i['title'] for i in data['insights']]
    assert 'Favorite Running Day' in titles, \
        f"Favorite Running Day should appear with 5 runs, but got: {titles}"


# ───────────────────────────────────────────────────────
# TEST 6: Typical Run — exact average
# ───────────────────────────────────────────────────────
def test_typical_run_exact_average(app, auth_client):
    """
    FIXTURE DATA:
      3 runs: 3.0 km, 5.0 km, 7.0 km → avg = 15.0 / 3 = 5.0 km

    EXPECTED:
      "Your average run distance is 5.0 km."
    """
    today = date.today()
    runs = [
        ((today - timedelta(days=i)).strftime("%Y-%m-%d"), dist, 6.0, 30.0)
        for i, dist in enumerate([3.0, 5.0, 7.0])
    ]
    _seed_runs(app, runs)

    resp = auth_client.get('/api/analytics/insights')
    data = resp.get_json()

    typical = next((i for i in data['insights'] if i['title'] == 'Your Typical Run'), None)
    assert typical is not None
    assert "5.0 km" in typical['description'], \
        f"Expected average 5.0 km, got: {typical['description']}"


# ───────────────────────────────────────────────────────
# TEST 7: Best Performance — exact pace formatting
# ───────────────────────────────────────────────────────
def test_best_performance_exact_pace(app, auth_client):
    """
    FIXTURE DATA:
      3 runs with paces: 7.5, 5.5, 6.0
      Best pace = 5.5 → formatted as 5:30 min/km

    EXPECTED:
      "Your fastest recorded pace is 5:30 min/km."
    """
    today = date.today()
    runs = [
        ((today - timedelta(days=0)).strftime("%Y-%m-%d"), 5.0, 7.5, 37.5),
        ((today - timedelta(days=1)).strftime("%Y-%m-%d"), 5.0, 5.5, 27.5),
        ((today - timedelta(days=2)).strftime("%Y-%m-%d"), 5.0, 6.0, 30.0),
    ]
    _seed_runs(app, runs)

    resp = auth_client.get('/api/analytics/insights')
    data = resp.get_json()

    best = next((i for i in data['insights'] if i['title'] == 'Best Performance'), None)
    assert best is not None
    assert "5:30 min/km" in best['description'], \
        f"Expected 5:30 min/km, got: {best['description']}"


# ───────────────────────────────────────────────────────
# TEST 8: Unauthenticated request returns 401
# ───────────────────────────────────────────────────────
def test_unauthenticated_returns_401(app, client):
    """The insights endpoint should require authentication."""
    resp = client.get('/api/analytics/insights')
    assert resp.status_code in (401, 302)  # 302 if redirecting to login


# ───────────────────────────────────────────────────────
# TEST 9: Consistency — exact active days count
# ───────────────────────────────────────────────────────
def test_consistency_active_days(app, auth_client):
    """
    FIXTURE DATA:
      3 runs on 3 different days this month, plus 1 duplicate day → 3 unique days

    EXPECTED:
      "You've been active on 3 days this month."
    """
    today = date.today()
    curr_month_start = today.replace(day=1)

    day1 = curr_month_start.strftime("%Y-%m-%d")
    day2 = (curr_month_start + timedelta(days=2)).strftime("%Y-%m-%d")
    day3 = (curr_month_start + timedelta(days=4)).strftime("%Y-%m-%d")

    runs = [
        (day1, 5.0, 6.0, 30.0),
        (day1, 3.0, 7.0, 21.0),  # same day as first — should not count twice
        (day2, 5.0, 6.0, 30.0),
        (day3, 5.0, 6.0, 30.0),
    ]
    _seed_runs(app, runs)

    resp = auth_client.get('/api/analytics/insights')
    data = resp.get_json()

    consistency = next((i for i in data['insights'] if i['title'] == 'Consistency'), None)
    assert consistency is not None
    assert "3 days" in consistency['description'], \
        f"Expected 3 days, got: {consistency['description']}"


# ───────────────────────────────────────────────────────
# TEST 10: Slower pace shows "Pace Change" not "Getting Faster"
# ───────────────────────────────────────────────────────
def test_slower_pace_shows_pace_change(app, auth_client):
    """
    FIXTURE DATA:
      Previous month: 2 runs with paces 5.0 and 5.0 → avg = 5.0 min/km
      Current month:  2 runs with paces 7.0 and 7.0 → avg = 7.0 min/km

    EXPECTED:
      pace_change_pct = ((5.0 - 7.0) / 5.0) * 100 = -40.0%
      Shows "Pace Change" with "40.0% slower"
    """
    today = date.today()
    curr_month_start = today.replace(day=1)
    prev_month_end = curr_month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)

    runs = [
        (prev_month_start.strftime("%Y-%m-%d"), 5.0, 5.0, 25.0),
        ((prev_month_start + timedelta(days=3)).strftime("%Y-%m-%d"), 5.0, 5.0, 25.0),
        (curr_month_start.strftime("%Y-%m-%d"), 5.0, 7.0, 35.0),
        ((curr_month_start + timedelta(days=3)).strftime("%Y-%m-%d"), 5.0, 7.0, 35.0),
    ]
    _seed_runs(app, runs)

    resp = auth_client.get('/api/analytics/insights')
    data = resp.get_json()
    titles = [i['title'] for i in data['insights']]

    assert 'Getting Faster' not in titles
    pace_change = next((i for i in data['insights'] if i['title'] == 'Pace Change'), None)
    assert pace_change is not None
    assert "40.0% slower" in pace_change['description'], \
        f"Expected 40.0% slower, got: {pace_change['description']}"
