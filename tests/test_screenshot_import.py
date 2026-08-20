"""
Tests for /api/parse-screenshot and /api/confirm-screenshot-import routes.
All Gemini API calls are mocked — no real API calls are made during tests.
"""

import pytest
import io
import json
import os
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_png():
    """Return a tiny valid-ish PNG byte string (just enough to pass size check)."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _mock_gemini_response(text):
    """Build a fake Gemini generate_content() return value."""
    res = MagicMock()
    res.text = text
    return res


VALID_JSON = json.dumps({
    "distance_km": 10.5,
    "duration_seconds": 3600,
    "pace_per_km": "5:43",
    "date": "2026-08-15",
    "calories": 620,
    "average_heart_rate": 152,
    "elevation_gain_m": 45.0,
    "source_app": "Strava",
})


# ---------------------------------------------------------------------------
# parse-screenshot tests
# ---------------------------------------------------------------------------

class TestParseScreenshot:

    def test_unauthenticated_returns_401(self, client):
        """No session → 401."""
        resp = client.post("/api/parse-screenshot")
        assert resp.status_code == 401

    def test_no_file_returns_400(self, auth_client):
        """No file field → 400."""
        resp = auth_client.post("/api/parse-screenshot", data={})
        assert resp.status_code == 400
        assert b"No file" in resp.data

    def test_wrong_file_type_returns_400(self, auth_client):
        """Uploading a .csv file → 400."""
        data = {"file": (io.BytesIO(b"col1,col2\n1,2"), "data.csv", "text/csv")}
        resp = auth_client.post(
            "/api/parse-screenshot",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        res = resp.get_json()
        assert "image" in res["error"].lower() or "supported" in res["error"].lower()

    def test_file_too_large_returns_400(self, auth_client):
        """File larger than 10 MB → 400."""
        big = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * (11 * 1024 * 1024))
        data = {"file": (big, "big.png", "image/png")}
        resp = auth_client.post(
            "/api/parse-screenshot",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert b"10 MB" in resp.data

    def test_missing_api_key_returns_503(self, auth_client):
        """No GEMINI_API_KEY → 503."""
        data = {"file": (io.BytesIO(_fake_png()), "run.png", "image/png")}
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            resp = auth_client.post(
                "/api/parse-screenshot",
                data=data,
                content_type="multipart/form-data",
            )
        assert resp.status_code == 503

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    def test_successful_parse_returns_preview(self, auth_client):
        """Happy path: mock returns valid JSON → 200 with data."""
        fake_msg = _mock_gemini_response(VALID_JSON)

        with patch("google.genai.Client") as MockClientClass:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = fake_msg
            MockClientClass.return_value = mock_client

            data = {"file": (io.BytesIO(_fake_png()), "strava.png", "image/png")}
            resp = auth_client.post(
                "/api/parse-screenshot",
                data=data,
                content_type="multipart/form-data",
            )

        assert resp.status_code == 200
        res = resp.get_json()
        assert res["success"] is True
        assert res["data"]["distance_km"] == pytest.approx(10.5)
        assert res["data"]["duration_seconds"] == 3600
        assert res["data"]["time_min"] == pytest.approx(60.0)
        assert res["data"]["source_app"] == "Strava"

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    def test_malformed_json_response_returns_422(self, auth_client):
        """Model returns garbled text → 422 user-friendly error."""
        fake_msg = _mock_gemini_response("Sorry, I cannot read that image. 🤖")

        with patch("google.genai.Client") as MockClientClass:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = fake_msg
            MockClientClass.return_value = mock_client

            data = {"file": (io.BytesIO(_fake_png()), "blur.png", "image/png")}
            resp = auth_client.post(
                "/api/parse-screenshot",
                data=data,
                content_type="multipart/form-data",
            )

        assert resp.status_code == 422
        res = resp.get_json()
        assert "screenshot" in res["error"].lower() or "clearly" in res["error"].lower()

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    def test_missing_required_fields_returns_422(self, auth_client):
        """Model returns JSON with null required fields → 422."""
        bad_json = json.dumps({
            "distance_km": None,
            "duration_seconds": None,
            "pace_per_km": "5:00",
            "date": None,
            "calories": None,
            "average_heart_rate": None,
            "elevation_gain_m": None,
            "source_app": "Garmin",
        })
        fake_msg = _mock_gemini_response(bad_json)

        with patch("google.genai.Client") as MockClientClass:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = fake_msg
            MockClientClass.return_value = mock_client

            data = {"file": (io.BytesIO(_fake_png()), "garmin.png", "image/png")}
            resp = auth_client.post(
                "/api/parse-screenshot",
                data=data,
                content_type="multipart/form-data",
            )

        assert resp.status_code == 422

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    def test_markdown_fenced_json_is_parsed(self, auth_client):
        """Model wraps JSON in ```json fences → still parsed correctly."""
        fenced = f"```json\n{VALID_JSON}\n```"
        fake_msg = _mock_gemini_response(fenced)

        with patch("google.genai.Client") as MockClientClass:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = fake_msg
            MockClientClass.return_value = mock_client

            data = {"file": (io.BytesIO(_fake_png()), "nike.png", "image/png")}
            resp = auth_client.post(
                "/api/parse-screenshot",
                data=data,
                content_type="multipart/form-data",
            )

        assert resp.status_code == 200
        res = resp.get_json()
        assert res["success"] is True

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    def test_api_exception_returns_502(self, auth_client):
        """Gemini raises an exception → 502 user-friendly error (not 500)."""
        with patch("google.genai.Client") as MockClientClass:
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = Exception("connection refused")
            MockClientClass.return_value = mock_client

            data = {"file": (io.BytesIO(_fake_png()), "run.png", "image/png")}
            resp = auth_client.post(
                "/api/parse-screenshot",
                data=data,
                content_type="multipart/form-data",
            )

        assert resp.status_code == 502
        res = resp.get_json()
        assert "AI service" in res["error"] or "manually" in res["error"]


# ---------------------------------------------------------------------------
# confirm-screenshot-import tests
# ---------------------------------------------------------------------------

VALID_PAYLOAD = {
    "distance_km": 10.5,
    "time_min": 60.0,
    "date": "2026-08-01",
    "run_type": "easy",
    "notes": "Great run",
    "source_app": "Strava",
}


class TestConfirmScreenshotImport:

    def test_unauthenticated_returns_401(self, client):
        resp = client.post(
            "/api/confirm-screenshot-import",
            json=VALID_PAYLOAD,
        )
        assert resp.status_code == 401

    def test_valid_payload_inserts_run(self, auth_client):
        """Valid payload → 200, run_id present."""
        resp = auth_client.post(
            "/api/confirm-screenshot-import",
            json=VALID_PAYLOAD,
        )
        assert resp.status_code == 200
        res = resp.get_json()
        assert res["success"] is True
        assert res.get("run_id") is not None
        assert "Strava" in res["message"]

    def test_future_date_returns_400(self, auth_client):
        payload = {**VALID_PAYLOAD, "date": "2099-12-31"}
        resp = auth_client.post("/api/confirm-screenshot-import", json=payload)
        assert resp.status_code == 400
        assert b"future" in resp.data

    def test_zero_distance_returns_400(self, auth_client):
        payload = {**VALID_PAYLOAD, "distance_km": 0}
        resp = auth_client.post("/api/confirm-screenshot-import", json=payload)
        assert resp.status_code == 400

    def test_negative_distance_returns_400(self, auth_client):
        payload = {**VALID_PAYLOAD, "distance_km": -5}
        resp = auth_client.post("/api/confirm-screenshot-import", json=payload)
        assert resp.status_code == 400

    def test_excessive_distance_returns_400(self, auth_client):
        payload = {**VALID_PAYLOAD, "distance_km": 999}
        resp = auth_client.post("/api/confirm-screenshot-import", json=payload)
        assert resp.status_code == 400

    def test_zero_duration_returns_400(self, auth_client):
        payload = {**VALID_PAYLOAD, "time_min": 0}
        resp = auth_client.post("/api/confirm-screenshot-import", json=payload)
        assert resp.status_code == 400

    def test_invalid_date_format_returns_400(self, auth_client):
        payload = {**VALID_PAYLOAD, "date": "15-08-2026"}
        resp = auth_client.post("/api/confirm-screenshot-import", json=payload)
        assert resp.status_code == 400

    def test_invalid_run_type_falls_back_to_easy(self, auth_client):
        """Unknown run_type is silently coerced to 'easy' — should still succeed."""
        payload = {**VALID_PAYLOAD, "run_type": "sprint"}
        resp = auth_client.post("/api/confirm-screenshot-import", json=payload)
        assert resp.status_code == 200

    def test_notes_tagged_with_source_app(self, auth_client):
        """Confirm the inserted run's notes contain the Screenshot Import tag."""
        from db import get_db
        payload = {**VALID_PAYLOAD, "source_app": "Nike Run Club", "notes": "morning"}
        resp = auth_client.post("/api/confirm-screenshot-import", json=payload)
        assert resp.status_code == 200
        run_id = resp.get_json()["run_id"]

        conn = get_db()
        row = conn.execute("SELECT notes FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()
        notes_val = row["notes"] if hasattr(row, "keys") else row[0]
        assert "[Screenshot Import" in notes_val
        assert "Nike Run Club" in notes_val

    def test_missing_date_defaults_to_today(self, auth_client):
        """Omitting date → today's date is used, not a future date error."""
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "date"}
        resp = auth_client.post("/api/confirm-screenshot-import", json=payload)
        assert resp.status_code == 200
