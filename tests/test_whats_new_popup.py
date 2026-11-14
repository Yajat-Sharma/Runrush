"""Tests for What's New Release Updates Popup.

Validates:
1. Template structure and absence of inline on* handlers (CSP compliance).
2. Presence of nonce="{{ csp_nonce() }}" on script and style blocks.
3. Coverage of the 5 new updates:
   - Live Voice Coach
   - GPS Route Trails & Shape Cards
   - 6-Section Workout Summary & Splits
   - Runner Spotlight & Quick-Log
   - Group Challenges V2
4. Login sets `just_logged_in` session flag.
5. Index route consumes `just_logged_in` and renders the modal when active.
6. 5-day expiration boundary logic.
"""

from datetime import datetime, timezone
from pathlib import Path
import re
import pytest

from app import app as flask_app, WHATS_NEW_EXPIRES
from db import get_db

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def test_whats_new_modal_template_structure_and_csp():
    """Verify _whats_new_modal.html exists, has no inline on* handlers, and uses csp_nonce()."""
    modal_path = TEMPLATES_DIR / "partials" / "_whats_new_modal.html"
    assert modal_path.exists(), "_whats_new_modal.html must exist"
    content = modal_path.read_text(encoding="utf-8")

    # CSP checks: No inline on* attributes
    on_handlers = re.findall(r'\b(on[a-zA-Z]+)\s*=', content)
    assert not on_handlers, f"Found inline on* handlers in _whats_new_modal.html: {on_handlers}"

    # No javascript: URLs
    assert "javascript:" not in content.lower(), "Found javascript: pseudo-URL in _whats_new_modal.html"

    # All script and style tags have nonce="{{ csp_nonce() }}"
    for tag in re.findall(r'<(?:script|style)\b[^>]*>', content, re.IGNORECASE):
        assert 'nonce="{{ csp_nonce() }}"' in tag or 'nonce=\'{{ csp_nonce() }}\'' in tag, (
            f"Tag missing csp_nonce: {tag}"
        )

    # Required structure and elements
    assert 'id="whatsNewModal"' in content
    assert 'data-action="dismissWhatsNewModal"' in content
    assert 'data-action="exploreWhatsNewFeatures"' in content
    assert 'data-action="handleWhatsNewBackdrop"' in content
    assert 'data-just-logged-in=' in content

    # 5 Key Update Highlights
    assert "Live Voice Coach" in content
    assert "GPS Route Trails & Shape Cards" in content or "Route Trails" in content
    assert "6-Section Workout Summary & Splits" in content or "Workout Summary" in content
    assert "Runner Spotlight" in content
    assert "Group Challenges" in content


def test_index_includes_whats_new_modal():
    """Verify index.html includes _whats_new_modal.html conditionally."""
    index_path = TEMPLATES_DIR / "index.html"
    content = index_path.read_text(encoding="utf-8")
    assert '{% if show_whats_new %}' in content
    assert '{% include "partials/_whats_new_modal.html" %}' in content


def test_whats_new_expiry_covers_next_5_days():
    """Verify WHATS_NEW_EXPIRES covers at least the next 5 days from Nov 14, 2026."""
    now_dt = datetime(2026, 11, 14, 21, 30, 0)
    assert WHATS_NEW_EXPIRES > now_dt
    delta = WHATS_NEW_EXPIRES - now_dt
    assert delta.days >= 5, f"WHATS_NEW_EXPIRES should be at least 5 days from Nov 14: got {delta.days} days"


def test_login_and_dashboard_display_whats_new(client):
    """Verify login sets just_logged_in flag and dashboard renders the What's New modal."""
    with flask_app.app_context():
        conn = get_db()
        from extensions import bcrypt
        hashed_pin = bcrypt.generate_password_hash("1234")
        if isinstance(hashed_pin, bytes):
            hashed_pin = hashed_pin.decode("utf-8")
        conn.execute("DELETE FROM users WHERE username = 'whatsnew_runner'")
        conn.execute(
            "INSERT INTO users (username, pin, display_name) VALUES ('whatsnew_runner', ?, 'Whats New Tester')",
            (hashed_pin,)
        )
        conn.commit()

    # Perform login
    resp = client.post("/login", data={"username": "whatsnew_runner", "pin": "1234"}, follow_redirects=False)
    assert resp.status_code == 302
    assert "/dashboard" in resp.headers["Location"] or resp.headers["Location"].endswith("/")

    # Check session has just_logged_in
    with client.session_transaction() as sess:
        assert sess.get("just_logged_in") is True
        assert sess.get("username") == "whatsnew_runner"

    # Visit dashboard
    dash_resp = client.get(resp.headers["Location"])
    assert dash_resp.status_code == 200
    html = dash_resp.get_data(as_text=True)

    # Modal should be rendered with data-just-logged-in="true"
    assert 'id="whatsNewModal"' in html
    assert 'data-just-logged-in="true"' in html
    assert "Live Voice Coach" in html

    # Subsequent visit to dashboard: just_logged_in should have been popped
    with client.session_transaction() as sess:
        assert "just_logged_in" not in sess

    second_resp = client.get("/dashboard")
    assert second_resp.status_code == 200
    second_html = second_resp.get_data(as_text=True)
    assert 'id="whatsNewModal"' in second_html
    assert 'data-just-logged-in="false"' in second_html
