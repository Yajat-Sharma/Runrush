from db import get_db


def test_voice_quick_log_requires_authentication(client):
    response = client.post(
        "/api/voice-quick-log",
        json={"distance": 5, "time_minutes": 28},
    )

    assert response.status_code == 401
    assert response.json["error"] == "Unauthorized"


def test_voice_quick_log_rejects_invalid_values(auth_client):
    response = auth_client.post(
        "/api/voice-quick-log",
        json={"distance": 0, "time_minutes": 28},
    )

    assert response.status_code == 400
    assert response.json["error"] == "Invalid distance or duration"


def test_voice_quick_log_saves_run(auth_client, app):
    response = auth_client.post(
        "/api/voice-quick-log",
        json={"distance": 5, "time_minutes": 28},
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    assert response.json["pace"] == 5.6

    with app.app_context():
        run = get_db().execute(
            "SELECT distance_km, time_min, pace, run_type, notes "
            "FROM runs WHERE notes = 'Voice quick log'"
        ).fetchone()

    assert tuple(run) == (5.0, 28.0, 5.6, "easy", "Voice quick log")


def test_voice_quick_log_allows_microphone_for_same_origin(client):
    response = client.get("/login")

    assert response.headers["Permissions-Policy"] == (
        "geolocation=(), microphone=(self), camera=()"
    )
