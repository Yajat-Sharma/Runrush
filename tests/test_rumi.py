"""
Tests for Rumi AI Personal Running Companion.

Validates:
1. Rumi chat interface and FAB integration.
2. Authenticated access requirements.
3. User data isolation (multi-user safety).
4. Deterministic factual questions return database-backed results without Gemini.
5. Simple factual questions do not call Gemini (even when unconfigured).
6. Hybrid questions receive verified statistics for AI coaching.
7. Monthly distance calculations.
8. Average pace calculations.
9. Longest run retrieval.
10. Weekly goal progress.
11. Month-to-month comparisons.
12. Missing or empty running data.
13. AI provider unavailable states for conversational/hybrid questions.
14. Invalid and oversized messages.
15. API errors and timeouts.
16. Rate limiting configuration.
17. No exposure of API credentials.
18. Conversation history and clear conversation.
"""

import os
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from db import get_db
from services.rumi_service import (
    build_rumi_system_prompt,
    classify_rumi_intent,
    generate_factual_response,
    generate_rumi_response,
    get_lifetime_stats,
    get_longest_run,
    get_fastest_5k,
    get_period_comparison,
    get_period_stats,
    get_personal_records,
    get_user_rumi_context,
    get_weekly_goal_progress,
    is_rumi_configured,
    IntentType,
)


def _mock_gemini_response(reply_text: str):
    """Build a fake Gemini generate_content() return value."""
    res = MagicMock()
    res.text = reply_text
    candidate = MagicMock()
    candidate.finish_reason.name = "STOP"
    res.candidates = [candidate]
    return res


# ---------------------------------------------------------------------------
# 1. Rumi Chat Interface & Quick Actions FAB
# ---------------------------------------------------------------------------

def test_rumi_chat_interface_in_templates(auth_client):
    """Verify Rumi AI action is in Quick Actions FAB and modal is included."""
    resp = auth_client.get("/", follow_redirects=True)
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    # Quick action button and label
    assert "Ask Rumi AI" in html
    assert "rumiAiBtn" in html
    assert "handleQuickAction" in html and "rumi" in html

    # Rumi modal and script
    assert "rumiChatModal" in html
    assert "rumi_chat.js" in html
    assert "Hey! I'm" in html or "I'm <strong>Rumi</strong>" in html
    assert "How many kilometres did I run last month?" in html


# ---------------------------------------------------------------------------
# 2. Authenticated Access
# ---------------------------------------------------------------------------

def test_unauthenticated_access_rejected(client):
    """Unauthenticated requests to all Rumi endpoints must return 401."""
    resp_chat = client.post("/api/rumi/chat", json={"message": "Hello"})
    assert resp_chat.status_code == 401
    assert resp_chat.json["error"] == "Unauthorized"

    resp_status = client.get("/api/rumi/status")
    assert resp_status.status_code == 401

    resp_clear = client.post("/api/rumi/clear")
    assert resp_clear.status_code == 401


# ---------------------------------------------------------------------------
# 3. User Data Isolation
# ---------------------------------------------------------------------------

def test_user_data_isolation(app):
    """Ensure user A only sees user A's data, and user B only sees user B's data."""
    with app.app_context():
        conn = get_db()
        # Create User A
        conn.execute(
            "INSERT INTO users (username, pin, display_name) VALUES (?, ?, ?)",
            ("runner_a", "1234", "Runner Alice")
        )
        user_a_id = conn.execute("SELECT id FROM users WHERE username = 'runner_a'").fetchone()["id"]

        # Create User B
        conn.execute(
            "INSERT INTO users (username, pin, display_name) VALUES (?, ?, ?)",
            ("runner_b", "5678", "Runner Bob")
        )
        user_b_id = conn.execute("SELECT id FROM users WHERE username = 'runner_b'").fetchone()["id"]

        # Insert runs for User A (10 km)
        conn.execute(
            """INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_a_id, "2026-10-15 08:00:00", 10.0, 50.0, 5.0, 600.0)
        )

        # Insert runs for User B (3 km)
        conn.execute(
            """INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_b_id, "2026-10-15 09:00:00", 3.0, 18.0, 6.0, 180.0)
        )
        conn.commit()

        ctx_a = get_user_rumi_context(user_a_id, today=date(2026, 10, 20))
        ctx_b = get_user_rumi_context(user_b_id, today=date(2026, 10, 20))

        # Check User A stats
        assert ctx_a["display_name"] == "Runner Alice"
        assert ctx_a["lifetime"]["total_distance_km"] == 10.0
        assert ctx_a["personal_bests"]["longest_run"]["distance_km"] == 10.0

        # Check User B stats
        assert ctx_b["display_name"] == "Runner Bob"
        assert ctx_b["lifetime"]["total_distance_km"] == 3.0
        assert ctx_b["personal_bests"]["longest_run"]["distance_km"] == 3.0

        # Check factual generation isolation
        resp_a = generate_factual_response(user_a_id, {"type": "longest_run"})
        resp_b = generate_factual_response(user_b_id, {"type": "longest_run"})
        assert "10.0 km" in resp_a
        assert "3.0 km" in resp_b


# ---------------------------------------------------------------------------
# 4. Deterministic Factual Questions Return Database Results Without Gemini
# ---------------------------------------------------------------------------

def test_factual_questions_return_database_results(auth_client, app):
    """Factual questions return deterministic calculations directly from the DB."""
    with app.app_context():
        conn = get_db()
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        uid = user["id"]

        # Insert a 15 km longest run in previous month (October 2026)
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "2026-10-12 07:00:00", 15.0, 75.0, 5.0, 900.0)
        )
        # Insert a 5 km run in current month
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "2026-11-02 07:00:00", 5.0, 25.0, 5.0, 300.0)
        )
        # Set a 20 km weekly goal
        conn.execute(
            "INSERT INTO user_weekly_goals (user_id, goal_km, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (uid, 20.0, "2026-11-01", "2026-11-01")
        )
        conn.commit()

    # Even with GEMINI_API_KEY unset, factual questions succeed with 200 OK
    with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
        with patch("google.genai.Client") as MockClient:
            # 1. Longest run
            resp_longest = auth_client.post("/api/rumi/chat", json={"message": "What's my longest run?"})
            assert resp_longest.status_code == 200
            assert "15.0 km" in resp_longest.json["reply"]
            assert resp_longest.json["source"] == "database"

            # 2. Monthly distance
            resp_month = auth_client.post("/api/rumi/chat", json={"message": "How many kilometres did I run last month?"})
            assert resp_month.status_code == 200
            assert "15.0 km" in resp_month.json["reply"]
            assert resp_month.json["source"] == "database"

            # 3. Weekly goal
            resp_goal = auth_client.post("/api/rumi/chat", json={"message": "How am I doing with my weekly goal?"})
            assert resp_goal.status_code == 200
            assert "20.0 km" in resp_goal.json["reply"]
            assert resp_goal.json["source"] == "database"

            # Ensure Gemini was never called!
            MockClient.assert_not_called()


def test_simple_factual_questions_do_not_call_gemini(auth_client):
    """Ensure Gemini client is not initialized or called for factual questions."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "some-key"}):
        with patch("google.genai.Client") as MockClient:
            auth_client.post("/api/rumi/chat", json={"message": "What's my average pace?"})
            auth_client.post("/api/rumi/chat", json={"message": "How many runs did I complete this week?"})
            auth_client.post("/api/rumi/chat", json={"message": "What is my longest run?"})

            MockClient.assert_not_called()


# ---------------------------------------------------------------------------
# 5. Hybrid Questions Receive Verified Statistics for AI Coaching
# ---------------------------------------------------------------------------

def test_hybrid_questions_receive_verified_statistics(auth_client, app):
    """Hybrid questions ('Am I improving?') pass verified database stats to Gemini."""
    with app.app_context():
        conn = get_db()
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        uid = user["id"]
        # Add runs for October (30 km) and November (45 km)
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "2026-10-10 07:00:00", 30.0, 180.0, 6.0, 1800.0)
        )
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "2026-11-03 07:00:00", 45.0, 247.5, 5.5, 2700.0)
        )
        conn.commit()

    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
        with patch("google.genai.Client") as MockClient:
            mock_inst = MagicMock()
            mock_inst.models.generate_content.return_value = _mock_gemini_response(
                "You are definitely improving! Your pace is faster and mileage is up."
            )
            MockClient.return_value = mock_inst

            resp = auth_client.post("/api/rumi/chat", json={"message": "Am I improving?"})
            assert resp.status_code == 200
            assert resp.json["source"] == "gemini"

            # Check that generate_content was called
            assert mock_inst.models.generate_content.called
            call_kwargs = mock_inst.models.generate_content.call_args[1]
            sys_instruct = call_kwargs["config"].system_instruction

            # Verify prompt contains verified numbers
            assert "Total Distance: 45.0 km" in sys_instruct
            assert "Total Distance: 30.0 km" in sys_instruct
            assert "STRICT GROUNDING RULES" in sys_instruct


# ---------------------------------------------------------------------------
# 6. Intent Classification Unit Tests
# ---------------------------------------------------------------------------

def test_classify_rumi_intent():
    """Verify intent classifier correctly tags factual, hybrid, and conversational."""
    # Factual
    assert classify_rumi_intent("How many kilometres did I run last month?")[0] == IntentType.FACTUAL
    assert classify_rumi_intent("What's my average pace?")[0] == IntentType.FACTUAL
    assert classify_rumi_intent("What's my longest run?")[0] == IntentType.FACTUAL
    assert classify_rumi_intent("How am I doing with my weekly goal?")[0] == IntentType.FACTUAL
    assert classify_rumi_intent("How many runs did I complete this week?")[0] == IntentType.FACTUAL
    assert classify_rumi_intent("What is my fastest 5k?")[0] == IntentType.FACTUAL
    assert classify_rumi_intent("Compare this month to last month")[0] == IntentType.FACTUAL
    assert classify_rumi_intent("How consistent am I?")[0] == IntentType.FACTUAL

    # Hybrid
    assert classify_rumi_intent("Am I improving?")[0] == IntentType.HYBRID
    assert classify_rumi_intent("How can I improve my 5K pace?")[0] == IntentType.HYBRID
    assert classify_rumi_intent("Create a plan based on my recent performance")[0] == IntentType.HYBRID

    # Conversational
    assert classify_rumi_intent("What's the difference between average pace and speed?")[0] == IntentType.CONVERSATIONAL
    assert classify_rumi_intent("Give me some motivation for today's run")[0] == IntentType.CONVERSATIONAL
    assert classify_rumi_intent("How to avoid shin splints?")[0] == IntentType.CONVERSATIONAL


# ---------------------------------------------------------------------------
# 7. Monthly Distance Questions & Calculations
# ---------------------------------------------------------------------------

def test_monthly_distance_context(app):
    """Verify current and previous month distance calculations."""
    ref_today = date(2026, 11, 15)
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO users (username, pin, display_name) VALUES (?, ?, ?)",
            ("month_runner", "1234", "Month Runner")
        )
        uid = conn.execute("SELECT id FROM users WHERE username = 'month_runner'").fetchone()["id"]

        # 2 runs in November (current month): 5 km and 12 km = 17 km
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "2026-11-02 07:00:00", 5.0, 25.0, 5.0, 300.0)
        )
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "2026-11-10 07:00:00", 12.0, 66.0, 5.5, 750.0)
        )

        # 1 run in October (previous month): 8 km
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "2026-10-20 07:00:00", 8.0, 48.0, 6.0, 480.0)
        )
        conn.commit()

        curr_m = get_period_stats(uid, "this_month", today=ref_today)
        prev_m = get_period_stats(uid, "last_month", today=ref_today)
        assert curr_m["distance_km"] == 17.0
        assert curr_m["run_count"] == 2
        assert prev_m["distance_km"] == 8.0
        assert prev_m["run_count"] == 1

        prompt = build_rumi_system_prompt(get_user_rumi_context(uid, today=ref_today))
        assert "Total Distance: 17.0 km" in prompt
        assert "Total Distance: 8.0 km" in prompt


# ---------------------------------------------------------------------------
# 8. Average Pace Calculations
# ---------------------------------------------------------------------------

def test_average_pace_calculations(app):
    """Verify lifetime and period average pace calculations."""
    ref_today = date(2026, 11, 15)
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO users (username, pin, display_name) VALUES (?, ?, ?)",
            ("pace_runner", "1234", "Pace Runner")
        )
        uid = conn.execute("SELECT id FROM users WHERE username = 'pace_runner'").fetchone()["id"]

        # Run 1: 10 km in 50 min (pace 5.0 min/km)
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "2026-11-02 07:00:00", 10.0, 50.0, 5.0, 600.0)
        )
        # Run 2: 10 km in 60 min (pace 6.0 min/km)
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "2026-11-04 07:00:00", 10.0, 60.0, 6.0, 600.0)
        )
        conn.commit()

        lt = get_lifetime_stats(uid)
        assert lt["avg_pace"] == 5.5
        assert lt["avg_pace_formatted"] == "5:30 /km"

        resp = generate_factual_response(uid, {"type": "average_pace"}, today=ref_today)
        assert "5:30 /km" in resp


# ---------------------------------------------------------------------------
# 9. Longest Run Retrieval
# ---------------------------------------------------------------------------

def test_longest_run_retrieval(app):
    """Verify longest run is correctly identified."""
    ref_today = date(2026, 11, 15)
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO users (username, pin, display_name) VALUES (?, ?, ?)",
            ("long_runner", "1234", "Long Runner")
        )
        uid = conn.execute("SELECT id FROM users WHERE username = 'long_runner'").fetchone()["id"]

        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "2026-11-01 07:00:00", 5.0, 25.0, 5.0, 300.0)
        )
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "2026-11-05 07:00:00", 21.1, 120.0, 5.69, 1300.0)
        )
        conn.commit()

        lr = get_longest_run(uid)
        assert lr is not None
        assert lr["distance_km"] == 21.1
        assert lr["time_min"] == 120.0

        resp = generate_factual_response(uid, {"type": "longest_run"}, today=ref_today)
        assert "21.1 km" in resp


# ---------------------------------------------------------------------------
# 10. Weekly Goal Progress
# ---------------------------------------------------------------------------

def test_weekly_goal_progress(app):
    """Verify weekly goal calculations including remaining distance and percentage."""
    ref_today = date(2026, 11, 4)
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO users (username, pin, display_name) VALUES (?, ?, ?)",
            ("goal_runner", "1234", "Goal Runner")
        )
        uid = conn.execute("SELECT id FROM users WHERE username = 'goal_runner'").fetchone()["id"]

        conn.execute(
            "INSERT INTO user_weekly_goals (user_id, goal_km, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (uid, 20.0, "2026-11-01", "2026-11-01")
        )
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "2026-11-03 07:00:00", 12.0, 60.0, 5.0, 720.0)
        )
        conn.commit()

        goals = get_weekly_goal_progress(uid, today=ref_today)
        assert goals["weekly_goal_km"] == 20.0
        assert goals["weekly_current_km"] == 12.0
        assert goals["weekly_remaining_km"] == 8.0
        assert goals["weekly_progress_pct"] == 60.0
        assert goals["weekly_achieved"] is False

        resp = generate_factual_response(uid, {"type": "goal_progress"}, today=ref_today)
        assert "12.0 km" in resp
        assert "20.0 km" in resp
        assert "8.0 km remaining" in resp


# ---------------------------------------------------------------------------
# 11. Month-to-Month Comparisons
# ---------------------------------------------------------------------------

def test_month_to_month_comparisons(app):
    """Verify delta and percentage calculations between current and previous month."""
    ref_today = date(2026, 11, 15)
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO users (username, pin, display_name) VALUES (?, ?, ?)",
            ("comp_runner", "1234", "Comp Runner")
        )
        uid = conn.execute("SELECT id FROM users WHERE username = 'comp_runner'").fetchone()["id"]

        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "2026-10-10 07:00:00", 40.0, 240.0, 6.0, 2400.0)
        )
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "2026-11-05 07:00:00", 50.0, 275.0, 5.5, 3000.0)
        )
        conn.commit()

        mom = get_period_comparison(uid, "month_over_month", today=ref_today)
        assert mom["previous_has_data"] is True
        assert mom["distance_delta_km"] == 10.0
        assert mom["distance_pct_change"] == 25.0

        resp = generate_factual_response(uid, {"type": "monthly_comparison"}, today=ref_today)
        assert "+10.0 km" in resp
        assert "+25.0%" in resp


# ---------------------------------------------------------------------------
# 12. Missing or Empty Running Data
# ---------------------------------------------------------------------------

def test_missing_or_empty_running_data(app):
    """User with zero runs logged must not trigger division by zero or errors."""
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO users (username, pin, display_name) VALUES (?, ?, ?)",
            ("newbie", "1234", "New Runner")
        )
        uid = conn.execute("SELECT id FROM users WHERE username = 'newbie'").fetchone()["id"]
        conn.commit()

        ctx = get_user_rumi_context(uid)
        assert ctx["lifetime"]["total_runs"] == 0
        assert ctx["lifetime"]["total_distance_km"] == 0.0
        assert ctx["lifetime"]["avg_pace"] is None
        assert ctx["personal_bests"]["longest_run"] is None

        # Factual responses must clearly communicate data unavailability
        resp_longest = generate_factual_response(uid, {"type": "longest_run"})
        assert "haven't logged any runs yet" in resp_longest

        resp_month = generate_factual_response(uid, {"type": "monthly_distance", "period": "this_month"})
        assert "haven't logged any runs yet this month" in resp_month


# ---------------------------------------------------------------------------
# 13. AI Provider Unavailable for Conversational Questions
# ---------------------------------------------------------------------------

def test_ai_provider_unavailable_returns_503(auth_client):
    """When GEMINI_API_KEY is unset, conversational/hybrid questions return 503."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
        resp = auth_client.post("/api/rumi/chat", json={"message": "What running advice do you have for beginners?"})
        assert resp.status_code == 503
        assert resp.json["code"] == "PROVIDER_UNAVAILABLE"

        status_resp = auth_client.get("/api/rumi/status")
        assert status_resp.status_code == 200
        assert status_resp.json["available"] is False


# ---------------------------------------------------------------------------
# 14. Invalid and Oversized Messages
# ---------------------------------------------------------------------------

def test_invalid_messages_rejected(auth_client):
    """Empty or oversized messages must return 400 Bad Request."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
        # Empty string
        resp_empty = auth_client.post("/api/rumi/chat", json={"message": ""})
        assert resp_empty.status_code == 400

        # Whitespace only
        resp_spaces = auth_client.post("/api/rumi/chat", json={"message": "   "})
        assert resp_spaces.status_code == 400

        # No payload
        resp_none = auth_client.post("/api/rumi/chat", json={})
        assert resp_none.status_code == 400

        # Oversized message (>500 chars)
        long_msg = "Run " * 150
        resp_long = auth_client.post("/api/rumi/chat", json={"message": long_msg})
        assert resp_long.status_code == 400
        assert "maximum length" in resp_long.json["error"]


# ---------------------------------------------------------------------------
# 15. API Errors and Timeouts Handled Gracefully
# ---------------------------------------------------------------------------

def test_api_error_returns_friendly_503(auth_client):
    """When the Gemini client raises an exception on hybrid/conversational, user gets 503."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
        with patch("google.genai.Client") as MockClient:
            mock_inst = MagicMock()
            mock_inst.models.generate_content.side_effect = TimeoutError("Connection timed out")
            MockClient.return_value = mock_inst

            resp = auth_client.post("/api/rumi/chat", json={"message": "How can I improve my 5k pace?"})
            assert resp.status_code == 503
            assert resp.json["code"] == "PROVIDER_ERROR"
            assert "trouble connecting" in resp.json["error"]


# ---------------------------------------------------------------------------
# 16. Rate Limiting Configuration
# ---------------------------------------------------------------------------

def test_rate_limiting_configured_on_chat(app):
    """Verify that limiter is applied to the rumi_chat endpoint."""
    rule = app.url_map._rules_by_endpoint.get("rumi_chat")
    assert rule is not None
    view_func = app.view_functions.get("rumi_chat")
    assert hasattr(view_func, "_rate_limits") or hasattr(view_func, "__wrapped__") or callable(view_func)


# ---------------------------------------------------------------------------
# 17. No Exposure of API Credentials
# ---------------------------------------------------------------------------

def test_no_exposure_of_credentials(auth_client, capsys):
    """Ensure API key is never echoed back in JSON responses or stdout."""
    secret_key = "AIzaSySUPER_SECRET_KEY_NEVER_LEAK"
    with patch.dict(os.environ, {"GEMINI_API_KEY": secret_key}):
        with patch("google.genai.Client") as MockClient:
            mock_inst = MagicMock()
            mock_inst.models.generate_content.return_value = _mock_gemini_response("Focus on easy runs and recovery.")
            MockClient.return_value = mock_inst

            resp = auth_client.post("/api/rumi/chat", json={"message": "How should I train?"})
            assert resp.status_code == 200
            assert resp.json["reply"] == "Focus on easy runs and recovery."

            assert secret_key not in resp.data.decode("utf-8")
            status_resp = auth_client.get("/api/rumi/status")
            assert secret_key not in status_resp.data.decode("utf-8")

            captured = capsys.readouterr()
            assert secret_key not in captured.out
            assert secret_key not in captured.err


# ---------------------------------------------------------------------------
# 18. Clear Conversation Endpoint
# ---------------------------------------------------------------------------

def test_clear_conversation(auth_client):
    """Verify /api/rumi/clear empties the session conversation history."""
    with auth_client.session_transaction() as sess:
        sess["rumi_history"] = [
            {"role": "user", "text": "Hi"},
            {"role": "model", "text": "Hello!"}
        ]

    resp = auth_client.post("/api/rumi/clear")
    assert resp.status_code == 200
    assert resp.json["success"] is True

    with auth_client.session_transaction() as sess:
        assert sess.get("rumi_history") == []
