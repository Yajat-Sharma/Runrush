import re
from unittest.mock import patch


VALID_SUBSCRIPTION = {
    "endpoint": "https://push.example.test/subscription-1",
    "keys": {"p256dh": "p" * 32, "auth": "a" * 16},
}


def test_push_routes_require_authentication(client):
    response = client.post("/api/push/subscribe", json=VALID_SUBSCRIPTION)
    assert response.status_code == 401
    assert client.post("/api/push/unsubscribe", json=VALID_SUBSCRIPTION).status_code == 401
    assert client.post("/api/push/test", json={}).status_code == 401


def test_subscribe_is_idempotent_and_unsubscribe_is_scoped(auth_client):
    first = auth_client.post("/api/push/subscribe", json=VALID_SUBSCRIPTION)
    duplicate = auth_client.post("/api/push/subscribe", json=VALID_SUBSCRIPTION)
    assert first.status_code == 201
    assert duplicate.status_code == 200

    from db import get_db
    with auth_client.application.app_context():
        rows = get_db().execute("SELECT COUNT(*) AS count FROM web_push_subscriptions").fetchone()
        assert rows["count"] == 1

    response = auth_client.post("/api/push/unsubscribe", json=VALID_SUBSCRIPTION)
    assert response.status_code == 200


def test_invalid_subscription_payload_is_rejected(auth_client):
    response = auth_client.post("/api/push/subscribe", json={
        "endpoint": "https://push.example.test/missing-keys",
        "keys": {},
    })
    assert response.status_code == 400


def test_test_push_only_delivers_current_users_subscription(auth_client, monkeypatch):
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "private")
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:test@example.com")
    auth_client.post("/api/push/subscribe", json=VALID_SUBSCRIPTION)

    with patch("services.push_service.send_push") as send_push:
        response = auth_client.post("/api/push/test", json={})

    assert response.status_code == 200
    assert response.get_json()["sent"] == 1
    send_push.assert_called_once()
    assert send_push.call_args.args[0]["endpoint"] == VALID_SUBSCRIPTION["endpoint"]


def test_test_push_removes_expired_subscription(auth_client, monkeypatch):
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "private")
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:test@example.com")
    auth_client.post("/api/push/subscribe", json=VALID_SUBSCRIPTION)

    class ExpiredPush(Exception):
        response = type("Response", (), {"status_code": 410})()

    with patch("services.push_service.send_push", side_effect=ExpiredPush()):
        response = auth_client.post("/api/push/test", json={})

    assert response.status_code == 502
    with auth_client.application.app_context():
        from db import get_db
        row = get_db().execute(
            "SELECT COUNT(*) AS count FROM web_push_subscriptions"
        ).fetchone()
        assert row["count"] == 0


def test_test_push_reports_missing_configuration(auth_client, monkeypatch):
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("VAPID_SUBJECT", raising=False)
    auth_client.post("/api/push/subscribe", json=VALID_SUBSCRIPTION)

    response = auth_client.post("/api/push/test", json={})
    assert response.status_code == 503
    assert "not configured" in response.get_json()["error"]


def test_push_state_changing_routes_require_csrf(app, auth_client):
    app.config["WTF_CSRF_ENABLED"] = True
    response = auth_client.post("/api/push/subscribe", json=VALID_SUBSCRIPTION)
    assert response.status_code == 400

    page = auth_client.get("/settings")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
    response = auth_client.post(
        "/api/push/subscribe",
        json=VALID_SUBSCRIPTION,
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 201
