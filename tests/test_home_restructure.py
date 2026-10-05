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
from utils.dates import get_today


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
        'date': get_today().isoformat(), 'distance': str(distance),  # app's (UTC) day, as the leaderboard uses
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


class TestExportMovedToSettings:

    def test_export_link_in_settings_not_runs_tab(self, client):
        login_as(client, 'export_mover')
        dashboard = client.get('/dashboard').get_data(as_text=True)
        assert 'href="/export"' not in dashboard
        settings = client.get('/settings').get_data(as_text=True)
        assert 'id="sec-data"' in settings and 'href="/export"' in settings

    def test_export_still_downloads_csv(self, client):
        login_as(client, 'export_csv')
        log_run(client, 5.0, 30)
        res = client.get('/export')
        assert res.status_code == 200
        assert 'csv' in res.mimetype or res.headers.get('Content-Disposition', '').endswith('.csv')


class TestHomePopups:

    def test_feed_and_runner_popups_present(self, client):
        login_as(client, 'popup_user')
        page = client.get('/dashboard').get_data(as_text=True)
        assert 'id="feedModal"' in page and 'id="runnersModal"' in page
        assert 'data-bs-target="#feedModal"' in page and 'data-bs-target="#runnersModal"' in page


class TestThemeFollowsAccount:
    """Settings → Appearance choice applies on every page and every device."""

    def test_saved_theme_is_injected_on_every_logged_in_page(self, client):
        login_as(client, 'theme_light')
        assert client.post('/settings/theme', data={'theme': 'light'}).status_code == 200
        conn = get_db()
        run_id = None
        log_run(client, 5.0, 30)
        run_id = conn.execute(
            "SELECT r.id FROM runs r JOIN users u ON u.id = r.user_id WHERE u.username = 'theme_light'"
        ).fetchone()["id"]
        conn.close()
        for url in ['/dashboard', '/settings', '/leaderboard', '/u/theme_light', f'/edit/{run_id}']:
            page = client.get(url).get_data(as_text=True)
            assert 'var accountTheme = "light";' in page, url

    def test_no_saved_theme_falls_back_to_device(self, client):
        login_as(client, 'theme_unset')
        conn = get_db()
        conn.execute("UPDATE users SET theme = NULL WHERE username = 'theme_unset'")
        conn.commit()
        conn.close()
        page = client.get('/dashboard').get_data(as_text=True)
        assert 'var accountTheme = null;' in page

    def test_edit_and_onboarding_pages_support_light(self, client):
        for tpl in ('templates/edit.html', 'templates/onboarding.html'):
            with open(os.path.join(os.path.dirname(__file__), '..', tpl), encoding='utf-8') as f:
                src = f.read()
            assert 'partials/_theme_init.html' in src and 'js/theme.js' in src, tpl
            assert 'html[data-theme="light"]' in src, tpl


class TestDefaultTheme:
    """No saved choice -> follow the device; no device preference -> light."""

    def test_user_without_theme_gets_system_not_dark(self, client):
        login_as(client, 'theme_default')
        conn = get_db()
        conn.execute("UPDATE users SET theme = NULL WHERE username = 'theme_default'")
        conn.commit()
        conn.close()
        page = client.get('/dashboard').get_data(as_text=True)
        assert 'var serverTheme = "system";' in page
        assert 'var accountTheme = null;' in page

    def test_system_resolves_to_light_unless_device_prefers_dark(self, client):
        root = os.path.join(os.path.dirname(__file__), '..')
        init = open(os.path.join(root, 'templates/partials/_theme_init.html'), encoding='utf-8').read()
        js = open(os.path.join(root, 'static/js/theme.js'), encoding='utf-8').read()
        for src in (init, js):
            assert "matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'" in src
            assert "(prefers-color-scheme: light)').matches ? 'light' : 'dark'" not in src

    def test_logged_out_profile_defaults_to_system(self, client):
        login_as(client, 'theme_public')
        client.get('/logout')
        page = client.get('/u/theme_public').get_data(as_text=True)
        assert 'var serverTheme = "system";' in page


class TestLoggedOutPagesFollowTheme:
    """Login, signup, landing, PIN recovery, 403 and offline follow the device theme."""

    PAGES = ['login', 'register', 'landing', 'forgot_pin', 'forgot_pin_methods', 'forgot_pin_reset',
             'forgot_pin_verify', 'set_pin', '403', 'offline']

    def test_every_page_loads_theme_and_has_light_styles(self, client):
        root = os.path.join(os.path.dirname(__file__), '..', 'templates')
        for name in self.PAGES:
            src = open(os.path.join(root, f'{name}.html'), encoding='utf-8').read()
            assert 'partials/_theme_init.html' in src, name
            assert 'js/theme.js' in src, name
            assert ('partials/_auth_light.html' in src) or ('html[data-theme="light"]' in src), name

    @pytest.mark.parametrize('url', ['/', '/login', '/register', '/forgot-pin', '/offline'])
    def test_logged_out_pages_render_with_device_default(self, client, url):
        page = client.get(url).get_data(as_text=True)
        assert 'var accountTheme = null;' in page, url
        assert "prefers-color-scheme: dark)').matches ? 'dark' : 'light'" in page, url


class TestRunsTabCardsOnly:

    def test_no_view_switch_list_table_or_filter(self, client):
        login_as(client, 'cards_only')
        log_run(client, 5.0, 30)
        page = client.get('/dashboard').get_data(as_text=True)
        for gone in ['btnListView', 'btnCardsView', 'runsListView', 'filterModal', 'Apply Filter', 'setRunsView']:
            assert gone not in page, gone
        assert 'id="runsCardView"' in page and 'run-card-modern' in page


class TestBodyMetrics:
    """Height (stored in cm, typed in ft/in or cm), weight in kg, realistic BMI only."""

    def _profile(self, **over):
        data = {'display_name': 'Body Test', 'theme': 'system', 'weight': '70', 'height': '175.3'}
        data.update(over)
        return data

    def test_realistic_values_saved_in_cm(self, client):
        login_as(client, 'bm_ok')
        assert client.post('/settings/update', data=self._profile()).status_code in (200, 302)
        conn = get_db()
        row = conn.execute("SELECT height, weight FROM users WHERE username = 'bm_ok'").fetchone()
        conn.close()
        assert float(row['height']) == 175.3 and float(row['weight']) == 70

    @pytest.mark.parametrize('height,weight', [
        ('5.9', '70'),     # feet typed into a cm field
        ('175', '7'),      # weight far too low
        ('300', '70'),     # height too tall
        ('120', '200'),    # BMI ~139
        ('abc', '70'),     # not a number
    ])
    def test_unrealistic_values_rejected_and_not_saved(self, client, height, weight):
        login_as(client, 'bm_bad')
        client.post('/settings/update', data=self._profile())
        res = client.post('/settings/update', data=self._profile(height=height, weight=weight))
        assert res.status_code == 400
        assert "check your height and weight" in res.get_json()['error']
        conn = get_db()
        row = conn.execute("SELECT height, weight FROM users WHERE username = 'bm_bad'").fetchone()
        conn.close()
        assert float(row['height']) == 175.3 and float(row['weight']) == 70   # unchanged

    def test_forms_use_feet_switch_and_bmi_preview(self, client):
        login_as(client, 'bm_forms')
        settings = client.get('/settings').get_data(as_text=True)
        assert 'data-body-metrics="required"' in settings and 'js/body-metrics.js' in settings
        root = os.path.join(os.path.dirname(__file__), '..', 'templates')
        onboarding = open(os.path.join(root, 'onboarding.html'), encoding='utf-8').read()
        for src in (settings, onboarding):
            assert 'data-height-unit="ft"' in src and 'data-height-unit="cm"' in src
            assert 'data-bmi-preview' in src


class TestManualLogRun:
    """Slow saves made people tap "Log Run" twice — the repeat must not create a second run."""

    def _count(self, username):
        conn = get_db()
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM runs r JOIN users u ON u.id = r.user_id WHERE u.username = ?", (username,)
        ).fetchone()["n"]
        conn.close()
        return n

    def test_double_submit_logs_once(self, client):
        login_as(client, 'double_tap')
        for _ in range(3):
            log_run(client, 5.3, 31.5)
        assert self._count('double_tap') == 1

    def test_different_runs_same_day_both_logged(self, client):
        login_as(client, 'two_runs')
        log_run(client, 5.0, 30)
        log_run(client, 3.0, 20)
        assert self._count('two_runs') == 2

    def test_success_message_shown_as_toast_on_dashboard(self, client):
        login_as(client, 'toast_user')
        res = client.post('/add', data={'date': get_today().isoformat(), 'distance': '4', 'time': '24', 'run_type': 'easy'},
                          follow_redirects=True)
        page = res.get_data(as_text=True)
        assert 'id="flashStack"' in page and 'Run logged! 🎉' in page

    def test_saving_overlay_and_lock_present(self, client):
        login_as(client, 'overlay_user')
        page = client.get('/dashboard').get_data(as_text=True)
        assert 'id="runSavingOverlay"' in page and 'addRunForm.dataset.submitting' in page


def test_no_text_functions_on_timestamp_date_column():
    """runs.date is TIMESTAMP on production Postgres (TEXT on SQLite): substr(date...) must cast first."""
    import re
    root = os.path.join(os.path.dirname(__file__), '..')
    for rel in ['app.py', 'services/social_service.py']:
        src = open(os.path.join(root, rel), encoding='utf-8').read()
        assert not re.search(r"substr\(\s*(r\.)?(date|created_at)\s*,", src), rel
