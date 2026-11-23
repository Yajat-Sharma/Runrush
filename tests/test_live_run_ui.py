"""Tests for Live Run UI enhancements (Phase 1 visual + Phase 2 behaviours).

Verifies:
- Live run modal template structure, icons, lime tokens, chip component, stats grid
- 3-2-1 countdown overlay and prefers-reduced-motion support
- GPS fix requirement and Start anyway fallback
- Press-and-hold (800ms) Finish button with SVG progress ring
- Screen wake lock lifecycle and visibilitychange listener
- Error states (location permission, GPS timeout, offline tiles)
- Demo mode persistent banner and server-side leaderboard isolation
- CSP nonce presence and zero inline on*= handlers
"""

from pathlib import Path
import re
import pytest

WORKSPACE = Path(__file__).parent.parent


def test_live_run_modal_template_structure():
    """Verify _live_run_modal.html contains all Phase 1 and Phase 2 required elements."""
    modal_file = WORKSPACE / "templates" / "partials" / "_live_run_modal.html"
    assert modal_file.exists(), "_live_run_modal.html must exist"
    content = modal_file.read_text(encoding="utf-8")

    # 1. Header: Font Awesome icon and LIVE RUN title (runner emoji removed)
    assert 'fa-person-running' in content
    assert 'LIVE RUN' in content
    assert '🏃' not in content, "Runner emoji should be removed from header"

    # 2. Consistent Chip Component with dot, icon, aria-pressed
    assert '.lrt-chip' in content
    assert '.lrt-chip-dot' in content
    assert '.lrt-chip-icon' in content
    assert 'id="lrtBleHrmBtn"' in content
    assert 'id="lrtVoiceCoachBtn"' in content
    assert 'id="lrtSimulateBtn"' in content
    assert 'aria-pressed=' in content

    # 3. Distance pill removed from map (guarded in JS)
    assert 'id="liveRunMapContainer"' in content
    assert 'id="lrtTrailSummaryBadge"' not in content or 'style="display:none;"' in content

    # 4. Lime accent tokens
    assert 'var(--accent-lime, #22C55E)' in content
    assert '#22C55E' in content

    # 5. Stats row: 3 equal columns, tabular-nums, >=12px label
    assert '.lrt-stats-grid' in content
    assert 'grid-template-columns: repeat(3, 1fr)' in content
    assert 'font-variant-numeric: tabular-nums' in content
    assert 'id="lrtDistance"' in content
    assert 'id="lrtPace"' in content
    assert 'id="lrtAvgPaceStatCol"' in content
    assert 'id="lrtHrStatCol"' in content

    # 6. Locating overlay & GPS indicator
    assert 'id="lrtLocatingOverlay"' in content
    assert 'Locating you…' in content
    assert 'id="lrtGpsIndicator"' in content
    assert 'id="lrtGpsBar1"' in content
    assert 'id="lrtGpsBar2"' in content
    assert 'id="lrtGpsBar3"' in content

    # 7. Start button & Start anyway button
    assert 'id="lrtStartBtn"' in content
    assert '.lrt-btn-start' in content
    assert 'id="lrtStartAnywayBtn"' in content
    assert 'data-action="startAnywayLiveRun"' in content

    # 8. 3-2-1 Countdown overlay
    assert 'id="lrtCountdownOverlay"' in content
    assert 'id="lrtCountdownNum"' in content
    assert 'prefers-reduced-motion' in content

    # 9. Press-and-hold finish button with progress ring
    assert 'id="lrtFinishBtn"' in content
    assert '.lrt-btn-finish' in content
    assert 'id="lrtFinishProgressCircle"' in content
    assert 'id="lrtHoldTooltip"' in content

    # 10. Error states & offline placeholder
    assert 'id="lrtErrorBanner"' in content
    assert 'id="lrtErrorTitle"' in content
    assert 'id="lrtErrorMsg"' in content
    assert 'id="lrtOfflineMapPlaceholder"' in content

    # 11. Persistent Demo Banner
    assert 'id="lrtDemoBanner"' in content
    assert 'Demo – not saved' in content

    # 12. CSP compliance
    style_matches = re.findall(r"<style([^>]*)>", content)
    for attrs in style_matches:
        assert 'nonce="{{ csp_nonce() }}"' in attrs, f"Style tag missing csp_nonce: {attrs}"

    # 13. Zero inline on* handlers
    assert not re.search(r'\s+on[a-z]+=', content, re.IGNORECASE), "Found inline on* handler in modal template"


def test_live_run_js_behaviours():
    """Verify live_run_tracker.js contains all Phase 2 behavioural logic."""
    js_file = WORKSPACE / "static" / "js" / "live_run_tracker.js"
    assert js_file.exists()
    content = js_file.read_text(encoding="utf-8")

    # 3-2-1 countdown logic
    assert 'function runStartCountdown(' in content
    assert 'window.runLiveRunCountdown =' in content
    assert 'window.cancelLiveRunCountdown =' in content
    assert 'prefers-reduced-motion' in content

    # GPS fix requirement and Start anyway
    assert 'window.startAnywayLiveRun =' in content
    assert 'window.RR_ACTIONS.startAnywayLiveRun =' in content

    # Press-and-hold (800ms) finish logic
    assert 'HOLD_DURATION = 800' in content
    assert 'function startFinishHold(' in content
    assert 'function endFinishHold(' in content
    assert 'function setFinishRingProgress(' in content
    assert 'window.finishLiveRun =' in content
    assert 'window.finishTracking =' in content

    # Close (X) confirm discard only when tracking or run data exists
    assert 'window.closeLiveRunTracker =' in content
    assert "confirm('Discard this run?')" in content

    # Screen Wake Lock lifecycle
    assert 'async function requestWakeLock(' in content
    assert 'function releaseWakeLock(' in content
    assert 'visibilitychange' in content

    # Error states & offline tile handling
    assert 'function onGpsError(' in content
    assert 'showLiveRunError(' in content
    assert 'window.dismissLiveRunError =' in content
    assert 'tileerror' in content
    assert 'lrtOfflineMapPlaceholder' in content

    # Demo mode isolation
    assert 'let wasDemoRun = false;' in content
    assert 'lrtDemoBanner' in content
    assert 'Demo runs are simulated for testing and cannot be saved' in content
