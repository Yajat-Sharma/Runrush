"""
Tests for CSRF configuration, /api/csrf-token endpoint, and CSRF expiration behavior.
"""

import json
import pytest
from app import app as flask_app
from flask_wtf.csrf import generate_csrf, validate_csrf
from wtforms import ValidationError


def test_csrf_time_limit_configuration(app):
    """Verify that WTF_CSRF_TIME_LIMIT is set to None so CSRF tokens don't expire after 1 hour."""
    assert app.config.get("WTF_CSRF_TIME_LIMIT") is None


def test_api_csrf_token_endpoint(auth_client):
    """Verify that /api/csrf-token returns 200 and a valid CSRF token."""
    res = auth_client.get("/api/csrf-token")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "csrf_token" in data
    assert isinstance(data["csrf_token"], str)
    assert len(data["csrf_token"]) > 10


def test_csrf_protection_and_token_refresh(app):
    """
    With CSRF enabled:
    1. A POST to a protected API without CSRF token is rejected with 400 (CSRF error).
    2. Calling /api/csrf-token generates a valid token for the active session.
    3. Sending the POST with the obtained X-CSRFToken header passes CSRF verification.
    """
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()

    try:
        # Step 1: Log in
        login_res = client.post(
            "/login",
            data={"username": "testuser", "password": "correctpassword"},
            follow_redirects=False
        )
        # In case test login requires CSRF or bypass
        # Let's ensure session has user_id
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "testuser"

        # Step 2: POST without CSRF token to /api/challenges should fail with 400 CSRF error
        post_bad = client.post(
            "/api/challenges",
            json={"challenge_type": "DISTANCE", "opponent_id": 2},
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        assert post_bad.status_code == 400
        bad_json = post_bad.get_json()
        assert "CSRF" in bad_json.get("error", "")

        # Step 3: Fetch fresh CSRF token from /api/csrf-token
        token_res = client.get("/api/csrf-token")
        assert token_res.status_code == 200
        fresh_token = token_res.get_json()["csrf_token"]

        # Step 4: POST with valid X-CSRFToken should NOT fail with CSRF error
        post_good = client.post(
            "/api/challenges",
            json={
                "challenge_type": "DISTANCE",
                "opponent_id": 2,
                "start_date": "2026-11-12",
                "end_date": "2026-11-18",
                "challenge_timezone": "UTC"
            },
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": fresh_token
            }
        )
        # Should not be rejected by CSRF handler (status != 400 with CSRF error)
        good_json = post_good.get_json() or {}
        assert "CSRF" not in good_json.get("error", "")

    finally:
        app.config["WTF_CSRF_ENABLED"] = False


def test_csrf_token_does_not_expire_with_none_time_limit(app):
    """Verify that when WTF_CSRF_TIME_LIMIT is None, token remains valid even after time passes."""
    with app.test_request_context():
        from flask import session
        session["csrf_token"] = "mock_secret"
        token = generate_csrf()

        # Validate with time_limit=None: should not raise SignatureExpired
        validate_csrf(token, time_limit=None)
