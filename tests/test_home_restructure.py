"""
Regression tests for the Home restructure and the Pace Pet removal.

Home order: header (predicted run) -> Weekly Leaderboard -> Runners Feed ->
Goals & Progress -> Log Your Run -> Runners to Follow. Pace Pet and the
Edit Dashboard customisation are gone.
"""

import os
from datetime import date

import pytest
from db import get_db


def login_as(client, username, pin='1234'):
    client.get('/logout')
    client.post('/register', data={'username': username, 'pin': pin})
    client.post('/login', data={'username': username, 'pin': pin})
    conn = get_db()
    conn.execute(
        "UPDATE users SET display_name = ?, profile_emoji = '🏃', experience = 'beginner', "
        "primary_goal = 'fitness' WHERE username = ?", (username, username))
    conn.commit()
    conn.close()


def log_run(client, distance, time_min):
    r = client.post('/add', data={
        'date': date.today().isoformat(), 'distance': str(distance),
        'time': str(time_min), 'run_type': 'easy',
    })
    assert r.status_code in (200, 302)


def home_html(client):
    res = client.get('/dashboard')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    return html[html.index('<div id="homeView">'):html.index('<!-- /#homeView -->')]


class TestHomeLayout:

    def test_sections_in_spec_order(self, client):
        login_as(client, 'home_order')
        html = home_html(client)
        markers = ['id="heroPrediction"', 'id="weeklyLeaderboardCard"', 'id="runnersFeedCard"',
                   'id="goalsProgressCard"', 'id="quickStartSection"', 'id="suggestedRunnersCard"']
        positions = [html.index(m) for m in markers]
        assert positions == sorted(positions), dict(zip(markers, positions))

    def test_old_sections_removed(self, client):
        login_as(client, 'home_removed')
        html = home_html(client)
        for gone in ['id="topRunsCard"', 'id="quoteBanner"', 'id="predictionSection"',
                     'id="dashboardWidgetContainer"', 'editDashboardBtn', 'data-widget=']:
            assert gone not in html, gone

    def test_goals_progress_merges_weekly_goal_and_this_month(self, client):
        login_as(client, 'home_goals')
        log_run(client, 5.0, 30)
        html = home_html(client)
        card = html[html.index('id="goalsProgressCard"'):html.index('id="quickStartSection"')]
        assert 'Weekly Goal' in card and 'id="goalProgressContainer"' in card
        assert 'This Month' in card and 'id="monthKmValue"' in card
        assert '6:00 /km avg pace' in card

    def test_leaderboard_highlights_current_user(self, client):
        login_as(client, 'home_lb')
        log_run(client, 3.0, 18)
        html = home_html(client)
        card = html[html.index('id="weeklyLeaderboardCard"'):html.index('id="runnersFeedCard"')]
        assert 'dw-row-me' in card
        assert 'View full leaderboard' in card

    def test_prediction_includes_estimated_time(self, client):
        login_as(client, 'home_predict')
        for _ in range(3):
            log_run(client, 5.0, 30)
        data = client.get('/api/predict-next-run').get_json()
        assert data['prediction_km']
        assert data['predicted_time_min'] == round(data['prediction_km'] * 6.0)


class TestPacePetRemoved:

    def test_no_pet_ui_on_home(self, client):
        login_as(client, 'nopet_ui')
        page = client.get('/dashboard').get_data(as_text=True)
        for gone in ['adoptPetModal', 'petCollectionModal', 'petEvolutionModal',
                     'pacePetWidget', 'Pace Pet', 'loadPetStatus', '/api/pet']:
            assert gone not in page, gone

    @pytest.mark.parametrize('method,url', [
        ('get', '/api/pet-status'), ('post', '/api/adopt-pet'), ('get', '/api/pet-collection'),
        ('post', '/api/pet/switch'), ('post', '/api/pet/rename'),
        ('get', '/api/dashboard-layout'), ('post', '/api/dashboard-layout'),
    ])
    def test_pet_and_layout_endpoints_gone(self, client, method, url):
        login_as(client, 'nopet_api')
        assert getattr(client, method)(url).status_code == 404

    def test_logging_runs_still_works_without_pets(self, client):
        login_as(client, 'nopet_runs')
        log_run(client, 4.2, 25)
        conn = get_db()
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM runs r JOIN users u ON u.id = r.user_id WHERE u.username = 'nopet_runs'"
        ).fetchone()["n"]
        conn.close()
        assert n == 1

    def test_init_db_no_longer_creates_user_pets(self, client):
        conn = get_db()
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'user_pets'"
        ).fetchone()
        conn.close()
        assert row is None

    def test_migration_009_drops_only_user_pets(self, client):
        login_as(client, 'nopet_migrate')
        log_run(client, 5.0, 30)
        conn = get_db()
        conn.execute("CREATE TABLE user_pets (id INTEGER PRIMARY KEY, user_id INTEGER, pet_name TEXT)")
        conn.commit()

        path = os.path.join(os.path.dirname(__file__), '..', 'migrations', '009_drop_user_pets.sql')
        with open(path, encoding='utf-8') as f:
            conn.executescript(f.read())

        tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
        runs = conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"]
        conn.close()
        assert 'user_pets' not in tables
        assert {'users', 'runs', 'friends', 'run_likes'} <= tables
        assert runs >= 1
