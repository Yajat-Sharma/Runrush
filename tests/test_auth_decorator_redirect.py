"""
Regression: utils/decorators.py used url_for('auth.login'), but the app
registers no 'auth' blueprint -- the real endpoint is 'login' (/login). An
anonymous request to a decorator-protected web route raised BuildError (HTTP
500) instead of redirecting to the login page.
"""


def test_anonymous_admin_notifications_redirects_to_login(client):
    # /admin/notifications is protected by @login_required + @admin_required.
    r = client.get("/admin/notifications")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/login")


def test_anonymous_decorator_api_route_still_returns_401(client):
    # API paths keep their JSON 401; the fix must not change that branch.
    r = client.get("/api/admin/notifications")
    assert r.status_code == 401


def test_regular_user_still_forbidden_on_admin_notifications(auth_client):
    # Authorization is unchanged: logged-in non-admins get 403, not a redirect.
    r = auth_client.get("/admin/notifications")
    assert r.status_code == 403
