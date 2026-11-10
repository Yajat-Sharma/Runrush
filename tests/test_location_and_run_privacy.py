import json
import pytest
from datetime import datetime, date
from db import get_db


@pytest.fixture
def other_user(client):
    """Create a second user in the database."""
    conn = get_db()
    conn.execute(
        "INSERT INTO users (username, pin, display_name) VALUES (?, ?, ?)",
        ("runner_two", "hashed_pin", "Runner Two")
    )
    conn.commit()
    user = conn.execute("SELECT * FROM users WHERE username = 'runner_two'").fetchone()
    conn.close()
    return user


class TestRunPrivacyDefaults:

    def test_run_added_via_form_defaults_to_private(self, auth_client):
        """Newly added runs via /add must default to is_private = 1."""
        today = date.today().isoformat()
        resp = auth_client.post(
            "/add",
            data={
                "date": today,
                "distance": "5.0",
                "time": "25.0",
                "run_type": "easy",
                "notes": "Testing private default",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

        conn = get_db()
        run = conn.execute(
            "SELECT id, is_private FROM runs WHERE notes = 'Testing private default'"
        ).fetchone()
        conn.close()
        assert run is not None
        assert run["is_private"] == 1

    def test_run_added_can_be_explicitly_public(self, auth_client):
        """User can explicitly set is_private = 0."""
        today = date.today().isoformat()
        resp = auth_client.post(
            "/add",
            data={
                "date": today,
                "distance": "6.0",
                "time": "30.0",
                "run_type": "tempo",
                "notes": "Testing public run",
                "is_private": "0",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

        conn = get_db()
        run = conn.execute(
            "SELECT id, is_private FROM runs WHERE notes = 'Testing public run'"
        ).fetchone()
        conn.close()
        assert run is not None
        assert run["is_private"] == 0

    def test_voice_quick_log_defaults_to_private(self, auth_client):
        """Runs logged via voice quick log default to is_private = 1."""
        resp = auth_client.post(
            "/api/voice-quick-log",
            json={"distance": 4.2, "time_minutes": 22.0},
        )
        assert resp.status_code == 200
        run_id = resp.get_json()["run_id"]

        conn = get_db()
        run = conn.execute("SELECT is_private FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()
        assert run["is_private"] == 1

    def test_screenshot_confirm_defaults_to_private(self, auth_client):
        """Importing a run via screenshot defaults to is_private = 1."""
        payload = {
            "distance_km": 10.0,
            "time_min": 50.0,
            "date": date.today().isoformat(),
            "run_type": "easy",
            "source_app": "Strava",
        }
        resp = auth_client.post("/api/confirm-screenshot-import", json=payload)
        assert resp.status_code == 200
        run_id = resp.get_json()["run_id"]

        conn = get_db()
        run = conn.execute("SELECT is_private FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()
        assert run["is_private"] == 1

    def test_edit_run_updates_privacy(self, auth_client):
        """Editing a run allows changing its privacy setting."""
        conn = get_db()
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        row = conn.execute(
            """INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, is_private)
               VALUES (?, ?, 5.0, 25.0, 5.0, 300, 1) RETURNING id""",
            (user["id"], date.today().isoformat())
        ).fetchone()
        run_id = row["id"] if hasattr(row, "keys") else row[0]
        conn.commit()
        conn.close()

        # Update to public (is_private absent or 0)
        resp = auth_client.post(
            f"/edit/{run_id}",
            data={
                "date": date.today().isoformat(),
                "distance": "5.0",
                "time": "25.0",
                "is_private": "0",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

        conn = get_db()
        run = conn.execute("SELECT is_private FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()
        assert run["is_private"] == 0

    def test_toggle_run_privacy_api(self, auth_client):
        """Endpoint /api/run/<id>/privacy toggles or sets privacy."""
        conn = get_db()
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        row = conn.execute(
            """INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, is_private)
               VALUES (?, ?, 5.0, 25.0, 5.0, 300, 1) RETURNING id""",
            (user["id"], date.today().isoformat())
        ).fetchone()
        run_id = row["id"] if hasattr(row, "keys") else row[0]
        conn.commit()
        conn.close()

        # Toggle from 1 -> 0
        resp = auth_client.post(f"/api/run/{run_id}/privacy", json={})
        assert resp.status_code == 200
        assert resp.get_json()["is_private"] == 0

        # Toggle from 0 -> 1
        resp = auth_client.post(f"/api/run/{run_id}/privacy", json={})
        assert resp.status_code == 200
        assert resp.get_json()["is_private"] == 1

        # Explicit set
        resp = auth_client.post(f"/api/run/{run_id}/privacy", json={"is_private": False})
        assert resp.status_code == 200
        assert resp.get_json()["is_private"] == 0


class TestFeedAndSocialPrivacy:

    def test_private_runs_hidden_from_other_users_feed(self, client, auth_client, other_user):
        """A user's private runs must not appear in other runners' activity feed."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        today = date.today().isoformat()

        conn = get_db()
        user1 = conn.execute("SELECT id FROM users WHERE username != 'runner_two' LIMIT 1").fetchone()
        # User 1 has 1 private run and 1 public run
        conn.execute(
            """INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, created_at, is_private)
               VALUES (?, ?, 7.0, 35.0, 5.0, 420, ?, 1)""",
            (user1["id"], today, now_str)
        )
        conn.execute(
            """INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, created_at, is_private)
               VALUES (?, ?, 8.0, 40.0, 5.0, 480, ?, 0)""",
            (user1["id"], today, now_str)
        )
        conn.commit()
        conn.close()

        # Log in as other_user
        with client.session_transaction() as sess:
            sess["user_id"] = other_user["id"]
            sess["username"] = other_user["username"]

        resp = client.get("/api/feed")
        assert resp.status_code == 200
        feed = resp.get_json()

        distances = [r["distance_km"] for r in feed["runs"] if r["username"] != "runner_two"]
        # Public run (8.0 km) is in feed, private run (7.0 km) is NOT in feed
        assert 8.0 in distances
        assert 7.0 not in distances


class TestGpsRouteDeletionAndAccessControl:

    def test_delete_specific_run_route(self, auth_client):
        """User can delete GPS route for a specific run while keeping the run record."""
        conn = get_db()
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        row = conn.execute(
            """INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, is_private)
               VALUES (?, ?, 10.0, 50.0, 5.0, 600, 1) RETURNING id""",
            (user["id"], date.today().isoformat())
        ).fetchone()
        run_id = row["id"] if hasattr(row, "keys") else row[0]

        fake_route = [{"lat": 37.7749, "lng": -122.4194}, {"lat": 37.7750, "lng": -122.4195}]
        conn.execute(
            "INSERT INTO run_routes (run_id, route_json, total_distance_km) VALUES (?, ?, ?)",
            (run_id, json.dumps(fake_route), 10.0)
        )
        conn.commit()
        conn.close()

        # Verify route exists
        resp = auth_client.get(f"/api/run/{run_id}/route")
        assert resp.status_code == 200

        # Delete route
        resp = auth_client.delete(f"/api/run/{run_id}/route")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

        # Verify route is gone from run_routes
        resp = auth_client.get(f"/api/run/{run_id}/route")
        assert resp.status_code == 404

        # Verify the run itself is still preserved
        conn = get_db()
        run = conn.execute("SELECT distance_km, time_min FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()
        assert run is not None
        assert run["distance_km"] == 10.0

    def test_user_cannot_delete_or_view_other_user_route(self, app, auth_client, other_user):
        """A user cannot fetch or delete another user's GPS route (IDOR protection)."""
        with auth_client.session_transaction() as sess:
            owner_id = sess["user_id"]

        conn = get_db()
        row = conn.execute(
            """INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories)
               VALUES (?, ?, 5.0, 25.0, 5.0, 300) RETURNING id""",
            (owner_id, date.today().isoformat())
        ).fetchone()
        run_id = row["id"] if hasattr(row, "keys") else row[0]
        fake_route = [{"lat": 40.7128, "lng": -74.0060}, {"lat": 40.7129, "lng": -74.0061}]
        conn.execute(
            "INSERT INTO run_routes (run_id, route_json, total_distance_km) VALUES (?, ?, ?)",
            (run_id, json.dumps(fake_route), 5.0)
        )
        conn.commit()
        conn.close()

        # Create separate client for other_user
        other_client = app.test_client()
        with other_client.session_transaction() as sess:
            sess["user_id"] = other_user["id"]
            sess["username"] = other_user["username"]

        # Other user tries to view route -> 404
        get_resp = other_client.get(f"/api/run/{run_id}/route")
        assert get_resp.status_code == 404

        # Other user tries to delete route -> 404
        del_resp = other_client.delete(f"/api/run/{run_id}/route")
        assert del_resp.status_code == 404

        # Route should still exist for the real owner
        route_still_exists = auth_client.get(f"/api/run/{run_id}/route")
        assert route_still_exists.status_code == 200

    def test_delete_all_user_gps_data(self, auth_client):
        """User can delete all GPS and location tracking data across their entire account."""
        conn = get_db()
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        conn.execute(
            "UPDATE users SET home_latitude = 37.77, home_longitude = -122.41, home_city = 'San Francisco' WHERE id = ?",
            (user["id"],)
        )
        # Create two runs with routes
        r1 = conn.execute(
            """INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories)
               VALUES (?, ?, 5.0, 25.0, 5.0, 300) RETURNING id""",
            (user["id"], date.today().isoformat())
        ).fetchone()[0]
        r2 = conn.execute(
            """INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories)
               VALUES (?, ?, 10.0, 50.0, 5.0, 600) RETURNING id""",
            (user["id"], date.today().isoformat())
        ).fetchone()[0]

        fake_route = [{"lat": 1.0, "lng": 2.0}, {"lat": 1.1, "lng": 2.1}]
        conn.execute("INSERT INTO run_routes (run_id, route_json, total_distance_km) VALUES (?, ?, ?)", (r1, json.dumps(fake_route), 5.0))
        conn.execute("INSERT INTO run_routes (run_id, route_json, total_distance_km) VALUES (?, ?, ?)", (r2, json.dumps(fake_route), 10.0))
        conn.commit()
        conn.close()

        # Call delete all GPS data
        resp = auth_client.delete("/api/user/delete-gps-data")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

        # Verify all routes for user are deleted
        conn = get_db()
        routes = conn.execute(
            "SELECT COUNT(*) FROM run_routes WHERE run_id IN (?, ?)", (r1, r2)
        ).fetchone()[0]
        assert routes == 0

        # Verify home coordinates are cleared
        u = conn.execute("SELECT home_latitude, home_longitude, home_city FROM users WHERE id = ?", (user["id"],)).fetchone()
        conn.close()
        assert u["home_latitude"] is None
        assert u["home_longitude"] is None
        assert u["home_city"] is None
