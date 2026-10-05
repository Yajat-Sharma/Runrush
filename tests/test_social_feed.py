"""
Tests for the Home activity feed, run likes, follow lists, runner suggestions
and the social notifications (new follower, run liked, friend just ran).
"""

from datetime import date, datetime, timedelta

from db import get_db


# --- Helpers ---

def login_as(client, username, pin='1234'):
    client.get('/logout')
    client.post('/register', data={'username': username, 'pin': pin})
    client.post('/login', data={'username': username, 'pin': pin})


def log_run(client, distance, time_min, run_date=None):
    r = client.post('/add', data={
        'date': run_date or date.today().isoformat(),
        'distance': str(distance),
        'time': str(time_min),
        'run_type': 'easy',
    })
    assert r.status_code in (200, 302), r.status_code


def user_id(username):
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row["id"]


def latest_run_id(username):
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM runs WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id(username),)
    ).fetchone()
    conn.close()
    return row["id"]


def notifications_for(client):
    return client.get('/api/notifications').get_json()['notifications']


# --- Feed ---

class TestActivityFeed:

    def test_requires_login(self, client):
        assert client.get('/api/feed').status_code == 401

    def test_shows_everyones_recent_runs_newest_first(self, client):
        login_as(client, 'feed_amy')
        log_run(client, 5.0, 30)
        login_as(client, 'feed_ben')
        log_run(client, 3.0, 20)

        data = client.get('/api/feed').get_json()
        names = [r['username'] for r in data['runs']]
        assert names.index('feed_ben') < names.index('feed_amy')

        ben_run = next(r for r in data['runs'] if r['username'] == 'feed_ben')
        assert ben_run['is_own'] is True
        assert ben_run['minutes_ago'] is not None and ben_run['minutes_ago'] < 5
        amy_run = next(r for r in data['runs'] if r['username'] == 'feed_amy')
        assert amy_run['is_own'] is False
        assert amy_run['following'] is False

    def test_excludes_runs_logged_over_24h_ago(self, client):
        login_as(client, 'feed_old')
        log_run(client, 4.0, 25)
        run_id = latest_run_id('feed_old')
        old = (datetime.now() - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        conn.execute("UPDATE runs SET created_at = ? WHERE id = ?", (old, run_id))
        conn.commit()
        conn.close()

        ids = [r['id'] for r in client.get('/api/feed').get_json()['runs']]
        assert run_id not in ids

    def test_excludes_backdated_runs_logged_today(self, client):
        """Bulk-importing old runs must not flood the feed."""
        login_as(client, 'feed_import')
        log_run(client, 6.0, 40, run_date=(date.today() - timedelta(days=30)).isoformat())
        ids = [r['id'] for r in client.get('/api/feed').get_json()['runs']]
        assert latest_run_id('feed_import') not in ids

    def test_most_liked_runs_come_first(self, client):
        login_as(client, 'rank_a')
        log_run(client, 3.0, 20)
        a_run = latest_run_id('rank_a')
        login_as(client, 'rank_b')
        log_run(client, 21.1, 120)
        b_run = latest_run_id('rank_b')
        login_as(client, 'rank_c')
        log_run(client, 5.0, 30)  # newest, but no likes

        for fan in ('rank_fan1', 'rank_fan2'):
            login_as(client, fan)
            client.post(f'/api/runs/{a_run}/like')
        client.post(f'/api/runs/{b_run}/like')

        data = client.get('/api/feed').get_json()
        ids = [r['id'] for r in data['runs']]
        assert ids.index(a_run) < ids.index(b_run)          # 2 likes before 1 like
        assert ids.index(b_run) < ids.index(latest_run_id('rank_c'))  # liked before unliked
        assert data['top_run_ids'][:2] == [a_run, b_run]
        liked = {r['id'] for r in data['runs'] if r['like_count'] > 0}
        assert set(data['top_run_ids']) <= liked and len(data['top_run_ids']) <= 3


# --- Likes ---

class TestRunLikes:

    def test_like_unlike_is_idempotent_and_counted(self, client):
        login_as(client, 'like_owner')
        log_run(client, 5.0, 30)
        run_id = latest_run_id('like_owner')

        login_as(client, 'like_fan')
        assert client.post(f'/api/runs/{run_id}/like').get_json() == {
            'success': True, 'liked': True, 'like_count': 1}
        assert client.post(f'/api/runs/{run_id}/like').get_json()['like_count'] == 1

        feed_run = next(r for r in client.get('/api/feed').get_json()['runs'] if r['id'] == run_id)
        assert feed_run['liked'] is True and feed_run['like_count'] == 1

        assert client.delete(f'/api/runs/{run_id}/like').get_json()['like_count'] == 0
        assert client.delete(f'/api/runs/{run_id}/like').get_json()['like_count'] == 0

    def test_like_notifies_owner_once(self, client):
        login_as(client, 'like_owner2')
        log_run(client, 7.5, 45)
        run_id = latest_run_id('like_owner2')

        login_as(client, 'like_fan2')
        client.post(f'/api/runs/{run_id}/like')
        client.post(f'/api/runs/{run_id}/like')

        login_as(client, 'like_owner2')
        likes = [n for n in notifications_for(client) if n['type'] == 'LIKE']
        assert len(likes) == 1
        assert 'like_fan2' in likes[0]['message'] and '7.50 km' in likes[0]['message']

    def test_liking_own_run_does_not_notify(self, client):
        login_as(client, 'like_self')
        log_run(client, 5.0, 30)
        client.post(f'/api/runs/{latest_run_id("like_self")}/like')
        assert not [n for n in notifications_for(client) if n['type'] == 'LIKE']

    def test_unknown_run_returns_404(self, client):
        login_as(client, 'like_404')
        assert client.post('/api/runs/999999/like').status_code == 404

    def test_requires_login(self, client):
        assert client.post('/api/runs/1/like').status_code == 401


# --- Follow notifications, lists, suggestions ---

class TestFollowing:

    def test_follow_notifies_target(self, client):
        login_as(client, 'fol_target')
        login_as(client, 'fol_fan')
        client.post('/follow/fol_target')

        login_as(client, 'fol_target')
        follows = [n for n in notifications_for(client) if n['type'] == 'FOLLOW']
        assert len(follows) == 1 and 'fol_fan' in follows[0]['message']

    def test_followers_get_notified_when_friend_runs(self, client):
        login_as(client, 'run_star')
        login_as(client, 'run_fan')
        client.post('/follow/run_star')

        login_as(client, 'run_star')
        log_run(client, 5.0, 28)

        login_as(client, 'run_fan')
        runs = [n for n in notifications_for(client) if n['type'] == 'FRIEND_RUN']
        assert len(runs) == 1 and '5.00 km' in runs[0]['message']

    def test_backdated_run_does_not_notify_followers(self, client):
        login_as(client, 'old_star')
        login_as(client, 'old_fan')
        client.post('/follow/old_star')

        login_as(client, 'old_star')
        log_run(client, 5.0, 28, run_date=(date.today() - timedelta(days=10)).isoformat())

        login_as(client, 'old_fan')
        assert not [n for n in notifications_for(client) if n['type'] == 'FRIEND_RUN']

    def test_follower_and_following_lists(self, client):
        login_as(client, 'list_a')
        login_as(client, 'list_b')
        client.post('/follow/list_a')

        followers = client.get('/api/user/list_a/followers').get_json()['people']
        assert [p['username'] for p in followers] == ['list_b']
        assert followers[0]['is_self'] is True

        following = client.get('/api/user/list_b/following').get_json()['people']
        assert [p['username'] for p in following] == ['list_a']
        assert following[0]['following'] is True

        assert client.get('/api/user/nobody_here/followers').status_code == 404

    def test_suggestions_exclude_self_followed_and_inactive(self, client):
        login_as(client, 'sug_active')
        log_run(client, 5.0, 30)
        login_as(client, 'sug_followed')
        log_run(client, 5.0, 30)
        login_as(client, 'sug_idle')  # never ran

        login_as(client, 'sug_viewer')
        log_run(client, 5.0, 30)
        client.post('/follow/sug_followed')

        names = [r['username'] for r in client.get('/api/social/suggested').get_json()['runners']]
        assert 'sug_active' in names
        assert 'sug_followed' not in names
        assert 'sug_idle' not in names
        assert 'sug_viewer' not in names

    def test_old_social_feed_page_removed(self, client):
        login_as(client, 'page_viewer')
        assert client.get('/social-feed').status_code == 404

    def test_all_runners_lists_everyone_but_me_with_follow_state(self, client):
        login_as(client, 'all_idle')                 # never ran
        login_as(client, 'all_active')
        log_run(client, 8.0, 48)
        login_as(client, 'all_me')
        client.post('/follow/all_active')

        runners = client.get('/api/social/runners').get_json()['runners']
        by_name = {r['username']: r for r in runners}
        assert 'all_me' not in by_name
        assert by_name['all_active']['following'] is True
        assert by_name['all_idle']['following'] is False
        names = [r['username'] for r in runners]
        assert names.index('all_active') < names.index('all_idle')   # most active first

    def test_all_runners_requires_login(self, client):
        assert client.get('/api/social/runners').status_code == 401


class TestRunLikers:
    """Runs tab: like count on each run + who liked it."""

    def test_likers_newest_first_with_follow_state(self, client):
        login_as(client, 'likers_owner')
        log_run(client, 5.0, 30)
        run_id = latest_run_id('likers_owner')
        login_as(client, 'likers_a')
        client.post(f'/api/runs/{run_id}/like')
        login_as(client, 'likers_b')
        client.post(f'/api/runs/{run_id}/like')

        login_as(client, 'likers_owner')
        client.post('/follow/likers_a')
        data = client.get(f'/api/runs/{run_id}/likers').get_json()
        assert data['like_count'] == 2
        assert [p['username'] for p in data['likers']] == ['likers_b', 'likers_a']
        by_name = {p['username']: p for p in data['likers']}
        assert by_name['likers_a']['following'] is True
        assert by_name['likers_b']['following'] is False
        assert all(p['minutes_ago'] is not None for p in data['likers'])

    def test_unliked_run_has_no_likers(self, client):
        login_as(client, 'likers_none')
        log_run(client, 3.0, 20)
        data = client.get(f'/api/runs/{latest_run_id("likers_none")}/likers').get_json()
        assert data == {'likers': [], 'like_count': 0}

    def test_unknown_run_and_login_required(self, client):
        assert client.get('/api/runs/1/likers').status_code == 401
        login_as(client, 'likers_404')
        assert client.get('/api/runs/999999/likers').status_code == 404

    def test_like_count_shown_on_runs_tab_and_load_more(self, client):
        login_as(client, 'likes_tab')
        log_run(client, 5.0, 30)
        run_id = latest_run_id('likes_tab')
        login_as(client, 'likes_fan')
        client.post(f'/api/runs/{run_id}/like')

        login_as(client, 'likes_tab')
        page = client.get('/dashboard').get_data(as_text=True)
        assert f'data-likers-run="{run_id}"' in page
        api_run = next(r for r in client.get('/api/runs?offset=0&limit=15').get_json()['runs'] if r['id'] == run_id)
        assert api_run['like_count'] == 1
