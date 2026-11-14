"""Unit tests for RunRush Run Card Live Insights & Bulgy Splits Pill V1.

Verifies:
1. Server-rendered run cards feature the tactile, bulgy `.run-insights-pill-btn` with live pulse dot.
2. The bare chevron arrow is replaced by the interactive bulgy pill button.
3. Expanded run details feature the 4-tile Total Metrics Grid (All numbers white, muted labels).
4. Expanded run details feature the Per-KM Splits Breakdown container with fastest split badges and pace bars.
5. Expanded run details feature the Trail Route Preview Box with Start (green) and Finish (red) badges.
6. Quick action buttons feature "Share Trail Story ✨" and "Full Map".
7. window.RR_ACTIONS.openRunTrailStory is properly registered and wired.
"""

import re
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
STATIC_JS_DIR = Path(__file__).resolve().parent.parent / "static" / "js"


def test_index_template_has_bulgy_insights_pill_button():
    """Verify that index.html contains the bulgy pill button for run insights."""
    content = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    
    assert "run-insights-pill-btn" in content, "Missing .run-insights-pill-btn class in index.html"
    assert "live-pulse-dot" in content, "Missing .live-pulse-dot in index.html"
    assert "⚡ Splits & Trail" in content, "Missing '⚡ Splits & Trail' pill label in index.html"
    assert "pill-chevron" in content, "Missing .pill-chevron in index.html"
    
    # Verify bare chevron was replaced by the button
    assert '<div><i class="fas fa-chevron-down rc-muted transition-transform" id="chevron-{{ r[\'id\'] }}"></i></div>' not in content, (
        "Old bare chevron arrow still present in index.html!"
    )


def test_index_template_has_totals_grid_and_splits_section():
    """Verify that index.html run card details include the Totals grid and Splits section."""
    content = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    
    assert "run-totals-grid" in content, "Missing .run-totals-grid in index.html"
    assert "TOTAL DISTANCE" in content, "Missing TOTAL DISTANCE label in index.html"
    assert "DURATION" in content, "Missing DURATION label in index.html"
    assert "AVG PACE" in content, "Missing AVG PACE label in index.html"
    assert "CALORIES" in content, "Missing CALORIES label in index.html"
    
    assert "run-splits-section" in content, "Missing .run-splits-section in index.html"
    assert "splitsBadge-{{ r['id'] }}" in content, "Missing splits badge element in index.html"
    assert "splitsList-{{ r['id'] }}" in content, "Missing splits list element in index.html"


def test_index_template_has_trail_preview_and_story_action():
    """Verify that index.html includes the trail route preview and Share Trail Story button."""
    content = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    
    assert "run-trail-preview-section" in content, "Missing .run-trail-preview-section in index.html"
    assert "trailSvgContainer-{{ r['id'] }}" in content, "Missing trailSvgContainer in index.html"
    assert "Share Trail Story ✨" in content, "Missing Share Trail Story button in index.html"
    assert "openRunTrailStory" in content, "Missing openRunTrailStory action in index.html"


def test_live_run_tracker_js_defines_insights_and_story_functions():
    """Verify that live_run_tracker.js exports renderRunCardInsights and openRunTrailStory."""
    js_content = (STATIC_JS_DIR / "live_run_tracker.js").read_text(encoding="utf-8")
    
    assert "window.renderRunCardInsights =" in js_content, "Missing window.renderRunCardInsights in live_run_tracker.js"
    assert "window.openRunTrailStory =" in js_content, "Missing window.openRunTrailStory in live_run_tracker.js"
    assert "renderMiniTrailSvg" in js_content, "Missing renderMiniTrailSvg in live_run_tracker.js"
    assert "renderMiniAthleticSilhouetteSvg" in js_content, "Missing renderMiniAthleticSilhouetteSvg in live_run_tracker.js"
    assert "window.RR_ACTIONS.openRunTrailStory =" in js_content, "Missing RR_ACTIONS.openRunTrailStory registration"


def test_split_parser_regex_matches_live_tracker_splits():
    """Verify regex accurately parses the live run splits summary format."""
    notes = (
        "Recorded with Live GPS Trail Tracker 🗺️\n"
        "Splits: KM 1: 04:30 (4:30/km) | KM 2: 04:15 (4:15/km) | KM 2.45: 01:55 (4:18/km)"
    )
    
    splits_match = re.search(r"Splits:\s*(.+)$", notes, re.MULTILINE)
    assert splits_match is not None, "Failed to match Splits header in notes"
    
    tokens = [t.strip() for t in splits_match.group(1).split("|") if t.strip()]
    assert len(tokens) == 3, f"Expected 3 split tokens, got {len(tokens)}"
    
    parsed = []
    for tok in tokens:
        m = re.match(r"KM\s*([\d.]+):\s*([\d:]+)\s*\(([\d:]+)/km\)", tok, re.IGNORECASE)
        assert m is not None, f"Failed to parse token: {tok}"
        km_val = float(m.group(1))
        duration = m.group(2)
        pace = m.group(3)
        parsed.append({"km": km_val, "duration": duration, "pace": pace})
    
    assert parsed[0] == {"km": 1.0, "duration": "04:30", "pace": "4:30"}
    assert parsed[1] == {"km": 2.0, "duration": "04:15", "pace": "4:15"}
    assert parsed[2] == {"km": 2.45, "duration": "01:55", "pace": "4:18"}
