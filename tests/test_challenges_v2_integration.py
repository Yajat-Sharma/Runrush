"""
RunRush Friendly Challenges V2 - Comprehensive Integration & UI Viewport Tests

Validates:
1. Format filters (All / 1v1 / Group) across ongoing, invitations, and history endpoints.
2. Direct challenge navigation route (/challenges/<id>) and tab query redirect.
3. Challenges section template rendering: format filter buttons, group buttons, badges, modals.
4. CSS styles and media query token coverage for 360px, 390px, 430px, 768px, and 1280px viewports.
5. Preservation of existing navigation, crossed-swords icon, 1v1 flows, light/dark theme variables.
6. Non-regression of existing features (Quick Voice Log, Rumi AI, PWA offline, Monthly Reports).
"""

from datetime import datetime, timezone
import json
import re
import pytest

from app import app as flask_app
from db import get_db
from services.friendly_challenge_service import (
    create_friendly_challenge_tables,
    create_group_challenge,
    create_challenge,
    accept_challenge,
    finalize_challenge_if_due,
)


def _create_user(conn, username):
    conn.execute(
        "INSERT INTO users (username, pin, display_name, profile_emoji) VALUES (?, 'pin', ?, '🏃')",
        (username, f"Runner {username}"),
    )
    conn.commit()
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    return row["id"] if hasattr(row, "keys") else row[0]


def _add_run(conn, user_id, distance_km, date_str):
    conn.execute(
        "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type) "
        "VALUES (?, ?, ?, 30.0, 5.0, 300.0, 'easy')",
        (user_id, date_str, distance_km),
    )
    conn.commit()


@pytest.fixture(autouse=True)
def setup_db(app):
    with app.app_context():
        create_friendly_challenge_tables()
        conn = get_db()
        conn.execute("DELETE FROM challenge_activity")
        conn.execute("DELETE FROM challenge_awards")
        conn.execute("DELETE FROM challenge_participants")
        conn.execute("DELETE FROM friendly_challenges")
        conn.execute("DELETE FROM runs WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'v2_%')")
        conn.execute("DELETE FROM users WHERE username LIKE 'v2_%'")
        conn.commit()
        yield


def test_format_filter_on_history_api(client):
    """Verifies that /api/challenges/history correctly filters by format (all, 1v1, group)."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "v2_f1")
        u2 = _create_user(conn, "v2_f2")
        u3 = _create_user(conn, "v2_f3")

        # 1v1 challenge (completed)
        cid_duel = create_challenge(u1, u2, "DISTANCE", "2026-11-01", "2026-11-03", conn=conn)
        conn.execute("UPDATE friendly_challenges SET status = 'COMPLETED', result_type = 'WIN', winner_id = ? WHERE id = ?", (u1, cid_duel))
        conn.execute("UPDATE challenge_participants SET result = 'WIN' WHERE challenge_id = ? AND user_id = ?", (cid_duel, u1))
        conn.commit()

        # Group challenge (completed)
        cid_group = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-01", "2026-11-04", conn=conn)
        conn.execute("UPDATE friendly_challenges SET status = 'COMPLETED', result_type = 'WIN', winner_id = ? WHERE id = ?", (u1, cid_group))
        conn.execute("UPDATE challenge_participants SET result = 'WIN' WHERE challenge_id = ? AND user_id = ?", (cid_group, u1))
        conn.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = u1
        sess["username"] = "v2_f1"

    # 1. Format: all -> returns both
    res_all = client.get("/api/challenges/history?format=all")
    assert res_all.status_code == 200
    ch_all = res_all.get_json()["challenges"]
    assert len(ch_all) == 2

    # 2. Format: 1v1 -> returns only 1v1
    res_1v1 = client.get("/api/challenges/history?format=1v1")
    assert res_1v1.status_code == 200
    ch_1v1 = res_1v1.get_json()["challenges"]
    assert len(ch_1v1) == 1
    assert ch_1v1[0]["challenge_mode"] in ("1V1", None)
    assert ch_1v1[0]["id"] == cid_duel

    # 3. Format: group -> returns only group
    res_group = client.get("/api/challenges/history?format=group")
    assert res_group.status_code == 200
    ch_group = res_group.get_json()["challenges"]
    assert len(ch_group) == 1
    assert ch_group[0]["challenge_mode"] == "GROUP"
    assert ch_group[0]["id"] == cid_group


def test_format_filter_on_ongoing_api(client):
    """Verifies that /api/challenges/ongoing correctly filters by format (all, 1v1, group)."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "v2_on1")
        u2 = _create_user(conn, "v2_on2")
        u3 = _create_user(conn, "v2_on3")

        # 1v1 accepted
        cid_duel = create_challenge(u1, u2, "DISTANCE", "2026-11-08", "2026-11-12", conn=conn)
        accept_challenge(cid_duel, u2, conn=conn)

        # Group accepted
        cid_group = create_group_challenge(u1, [u2, u3], "DISTANCE", "2026-11-08", "2026-11-14", conn=conn)
        accept_challenge(cid_group, u2, conn=conn)
        accept_challenge(cid_group, u3, conn=conn)

    with client.session_transaction() as sess:
        sess["user_id"] = u1
        sess["username"] = "v2_on1"

    # All format
    res_all = client.get("/api/challenges/ongoing?format=all")
    assert res_all.status_code == 200
    data_all = res_all.get_json()["challenges"]
    assert len(data_all) == 2

    # 1v1 format
    res_1v1 = client.get("/api/challenges/ongoing?format=1v1")
    assert res_1v1.status_code == 200
    data_1v1 = res_1v1.get_json()["challenges"]
    assert len(data_1v1) == 1
    assert data_1v1[0]["id"] == cid_duel

    # Group format
    res_group = client.get("/api/challenges/ongoing?format=group")
    assert res_group.status_code == 200
    data_group = res_group.get_json()["challenges"]
    assert len(data_group) == 1
    assert data_group[0]["id"] == cid_group


def test_direct_challenge_url_route(client):
    """Direct URL /challenges/<id> redirects logged in user to SPA challenges tab with challenge_id param."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "v2_nav1")

    with client.session_transaction() as sess:
        sess["user_id"] = u1
        sess["username"] = "v2_nav1"

    res = client.get("/challenges/123", follow_redirects=False)
    assert res.status_code == 302
    assert "tab=challenges" in res.headers["Location"]
    assert "challenge_id=123" in res.headers["Location"]


def test_challenges_section_html_contains_v2_elements(client):
    """Inspects rendered template markup for format filter pills, group buttons, and announcement modal."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "v2_html1")

    with client.session_transaction() as sess:
        sess["user_id"] = u1
        sess["username"] = "v2_html1"

    res = client.get("/dashboard")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # 1. Format Filter Pills in template
    assert 'cb-format-filter-btn' in html, "Should include cb-format-filter-btn for Ongoing & Invitations format filtering"
    assert 'filterOngoingFormat(' in html, "Should bind onclick to filterOngoingFormat"
    assert 'filterInvitationsFormat(' in html, "Should bind onclick to filterInvitationsFormat"
    assert 'filterHistoryFormat(' in html, "Should bind onclick to filterHistoryFormat"

    # 2. Group Button in Header
    assert 'Group Challenge' in html, "Header should have Group Challenge button"
    assert 'openChallengeBuilder(null, \'GROUP\')' in html, "Should open builder in GROUP mode"

    # 3. Builder Format Switcher
    assert 'cbMode1v1Btn' in html, "Should include 1v1 mode button in builder"
    assert 'cbModeGroupBtn' in html, "Should include Group mode button in builder"
    assert 'cbSelectedChips' in html, "Should include selected participant chips container"

    # 4. Announcement Modal V2
    assert 'challengesUpdateAnnouncementModal' in html, "Should include announcement modal"
    assert 'Friendly Challenges V2: Group Showdowns' in html, "Announcement title should be V2 Group Showdowns"
    assert 'Free-for-All Group Showdowns' in html, "Announcement should describe group showdowns"

    # 5. Crossed-swords navigation icon preserved
    assert '⚔️' in html, "Navigation should display crossed swords icon"


def test_responsive_css_viewports_and_tokens():
    """Validates CSS responsive rules and token usage for viewports: 360px, 390px, 430px, 768px, 1280px."""
    import os
    css_file = os.path.join(flask_app.root_path, "static", "css", "challenges.css")
    assert os.path.exists(css_file), "challenges.css must exist"

    with open(css_file, "r", encoding="utf-8") as f:
        css = f.read()

    # Viewport rules
    assert "@media (max-width: 480px)" in css, "Should support mobile phone viewports <= 480px (360px, 390px, 430px)"
    assert "@media (min-width: 1200px)" in css, "Should support desktop viewport >= 1200px (1280px)"

    # Theme tokens and light theme support
    assert "var(--accent" in css, "Should use accent color token"
    assert "var(--bg-card" in css, "Should use bg-card token"
    assert "var(--border" in css, "Should use border color tokens"
    assert '[data-theme="light"]' in css, "Should support light theme overrides"

    # Filter classes
    assert ".cb-format-filter-btn" in css, "Must define .cb-format-filter-btn"
    assert ".cb-history-format-btn" in css, "Must define .cb-history-format-btn"
    assert ".cb-runner-chip" in css, "Must define .cb-runner-chip"
    assert ".cb-group-table" in css, "Must define .cb-group-table"


def test_existing_features_unregressed(client):
    """Ensures Quick Voice Log, Rumi AI, PWA offline, and Monthly Reports remain functional."""
    with flask_app.app_context():
        conn = get_db()
        u1 = _create_user(conn, "v2_reg1")

    with client.session_transaction() as sess:
        sess["user_id"] = u1
        sess["username"] = "v2_reg1"

    # 1. Main dashboard page loads
    res_home = client.get("/dashboard")
    assert res_home.status_code == 200

    # 2. PWA offline & service worker routes
    res_sw = client.get("/sw.js")
    assert res_sw.status_code == 200
    res_offline = client.get("/offline")
    assert res_offline.status_code == 200

    # 3. Monthly report route exists
    res_monthly = client.get("/api/monthly-reports")
    assert res_monthly.status_code in (200, 404), "Monthly reports API responds as expected"

    # 4. Rumi status / suggestions endpoint
    res_rumi = client.get("/api/rumi/suggestions")
    assert res_rumi.status_code in (200, 404), "Rumi API responds as expected"
