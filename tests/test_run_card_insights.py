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


def test_live_run_modal_and_card_have_redesigned_6_sections():
    """Verify both Completed Run review drawer and Run Details card implement the 6-section hierarchy."""
    live_modal = (TEMPLATES_DIR / "partials" / "_live_run_modal.html").read_text(encoding="utf-8")
    index_html = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    
    # 1. RUN HEADER
    assert "lrtRevDateTime" in live_modal
    assert "lrtRevZoneBadge" in live_modal
    assert "RUN HEADER" in index_html
    
    # 2. PERFORMANCE OVERVIEW
    assert "lrtReviewStatsGrid" in live_modal
    assert "run-totals-grid" in index_html
    
    # 3. KILOMETRE SPLITS
    assert "lrtSplitsContainer" in live_modal
    assert "run-splits-section" in index_html
    
    # 4. ROUTE TRAIL
    assert "lrtToggleMapBtn" in live_modal
    assert "run-trail-preview-section" in index_html
    
    # 5. SHARE YOUR RUN
    assert "lrtShareTrailCardBtn" in live_modal
    assert "run-share-prominent-card" in index_html
    assert "Share Trail Story ✨" in live_modal
    assert "Share Trail Story ✨" in index_html
    
    # 6. RUMI AI NOTES
    assert "lrtRumiNotesContainer" in live_modal
    assert "run-rumi-card" in index_html
    assert "Rumi AI Notes" in index_html


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


def test_runs_view_tag_balance_and_containment():
    """Verify that runsCardContainer loop doesn't have extra closing divs that leak runsView."""
    index_path = Path(__file__).resolve().parent.parent / "templates" / "index.html"
    content = index_path.read_text(encoding="utf-8")
    
    # Check that runsCardContainer starts inside runsView
    runs_view_pos = content.find('id="runsView"')
    runs_container_pos = content.find('id="runsCardContainer"')
    runs_view_close_pos = content.find('<!-- /#runsView -->')
    
    assert runs_view_pos != -1, "runsView not found"
    assert runs_container_pos != -1, "runsCardContainer not found"
    assert runs_view_close_pos != -1, "<!-- /#runsView --> not found"
    assert runs_view_pos < runs_container_pos < runs_view_close_pos, "runsCardContainer must be inside runsView"
    
    # Extract the jinja loop for runs (matching the outer loop that ends before total_runs_count)
    loop_start = content.find('{% for r in runs[:15] %}')
    marker = '{% endfor %}\n      </div>\n      {% if total_runs_count > 15 %}'
    loop_end_pos = content.find(marker, loop_start)
    assert loop_start != -1 and loop_end_pos != -1, "run loop outer boundaries not found"
    
    loop_html = content[loop_start:loop_end_pos]
    open_divs = loop_html.count('<div')
    close_divs = loop_html.count('</div>')
    assert open_divs == close_divs, f"Unbalanced divs inside run loop: {open_divs} opened, {close_divs} closed"

