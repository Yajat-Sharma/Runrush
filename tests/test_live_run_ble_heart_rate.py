"""Tests for Web Bluetooth Heart Rate Monitor (BLE) Pairing in Live Run Tracker.

Validates:
1. Template elements in _live_run_modal.html:
   - Bluetooth HRM pair button in top bar with CSP data-action="toggleBleHeartRate"
   - Live Heart Rate stat column with animated pulsing heart and zone label
   - Heart Rate & Intensity Zones review breakdown card with 5-zone stacked progress bar
   - Heartbeat keyframe animation in CSP nonced <style> block
   - Strict zero inline on* attributes (CSP compliance)
2. JavaScript definitions and actions in live_run_tracker.js:
   - Web Bluetooth API capability detection
   - 5-Zone intensity classification model (Z1 Recovery to Z5 VO2 Max)
   - Standard Bluetooth SIG GATT 0x2A37 Heart Rate Measurement parsing
   - Window exports: toggleBleHeartRate, getHeartRateState, RR_ACTIONS.toggleBleHeartRate
3. Python reference simulations for GATT packet decoding & Zone percentages.
"""

from pathlib import Path
import re
import pytest

WORKSPACE = Path(__file__).parent.parent


def test_ble_hrm_modal_template_structure_and_csp():
    """Verify _live_run_modal.html contains Bluetooth HRM button, live HR HUD, and review breakdown."""
    modal_file = WORKSPACE / "templates" / "partials" / "_live_run_modal.html"
    assert modal_file.exists(), "_live_run_modal.html must exist"
    content = modal_file.read_text(encoding="utf-8")

    # 1. Top Bar BLE HRM Toggle Button
    assert 'id="lrtBleHrmBtn"' in content, "Missing lrtBleHrmBtn top bar button"
    assert 'data-action="toggleBleHeartRate"' in content, "Missing toggleBleHeartRate data-action"
    assert 'id="lrtBleHrmIcon"' in content, "Missing lrtBleHrmIcon icon element"
    assert 'id="lrtBleHrmText"' in content, "Missing lrtBleHrmText text label"

    # 2. Live Run HUD Stats Column
    assert 'id="lrtHrStatCol"' in content, "Missing lrtHrStatCol in live stats row"
    assert 'id="lrtHeartRate"' in content, "Missing lrtHeartRate live BPM value display"
    assert 'id="lrtHrZoneLabel"' in content, "Missing lrtHrZoneLabel zone label"
    assert 'id="lrtHeartPulseIcon"' in content, "Missing lrtHeartPulseIcon heart icon"
    assert 'lrt-heartbeat' in content, "Missing lrt-heartbeat CSS class"

    # 3. Post-Run Review Heart Rate & 5-Zone Intensity Breakdown
    assert 'id="lrtHeartRateSection"' in content, "Missing lrtHeartRateSection in review drawer"
    assert 'id="lrtRevHrSummaryBadge"' in content, "Missing lrtRevHrSummaryBadge summary badge"
    assert 'id="lrtHrZoneStackedBar"' in content, "Missing lrtHrZoneStackedBar stacked progress bar"

    # 5 Zone Progress Bars
    for z in range(1, 6):
        assert f'id="lrtZoneBar{z}"' in content, f"Missing lrtZoneBar{z}"
        assert f'id="lrtZonePct{z}"' in content, f"Missing lrtZonePct{z}"

    # 4. CSS animations and CSP compliance
    assert '@keyframes lrtHeartbeat' in content, "Missing lrtHeartbeat keyframe animation"
    style_matches = re.findall(r"<style([^>]*)>", content)
    for attrs in style_matches:
        assert 'nonce="{{ csp_nonce() }}"' in attrs or 'nonce=\'{{ csp_nonce() }}\'' in attrs, (
            f"Style tag missing csp_nonce: {attrs}"
        )

    # 5. Zero inline on* event handlers
    assert not re.search(r'\s+on[a-z]+=', content, re.IGNORECASE), "Found inline on* handler in modal template"


def test_ble_hrm_js_definitions():
    """Verify that Web Bluetooth HRM state, GATT parsing, and methods exist in live_run_tracker.js."""
    js_file = WORKSPACE / "static" / "js" / "live_run_tracker.js"
    assert js_file.exists()
    content = js_file.read_text(encoding="utf-8")

    # State variables
    assert 'let bleDevice = null;' in content
    assert 'let bleConnected = false;' in content
    assert 'let currentHeartRate = null;' in content
    assert 'let hrSamples = [];' in content
    assert 'let maxHeartRateRecorded = 0;' in content
    assert 'let hrZoneSeconds =' in content

    # Helper & GATT methods
    assert 'function isWebBluetoothSupported()' in content
    assert 'function getHeartRateZone(bpm)' in content
    assert 'function parseHeartRateMeasurement(dataView)' in content
    assert 'function updateBleHrmUI()' in content
    assert 'function handleHeartRateReading(bpm)' in content
    assert 'function onBleDisconnected()' in content

    # Global window & CSP action bindings
    assert 'window.toggleBleHeartRate =' in content
    assert 'window.getHeartRateState =' in content
    assert 'window.RR_ACTIONS.toggleBleHeartRate =' in content


def test_permissions_policy_allows_bluetooth(client):
    """Verify Permissions-Policy header includes bluetooth=(self)."""
    resp = client.get("/")
    perm_policy = resp.headers.get("Permissions-Policy", "")
    assert "bluetooth=(self)" in perm_policy


def get_simulated_heart_rate_zone(bpm, max_hr=190):
    """Python reference simulator mirroring getHeartRateZone(bpm) in live_run_tracker.js."""
    if not bpm or bpm <= 0:
        return 0, "Inactive"
    pct = (bpm / max_hr) * 100.0
    if pct < 60:
        return 1, "Zone 1 (Recovery)"
    elif pct < 70:
        return 2, "Zone 2 (Aerobic)"
    elif pct < 80:
        return 3, "Zone 3 (Tempo)"
    elif pct < 90:
        return 4, "Zone 4 (Threshold)"
    else:
        return 5, "Zone 5 (VO2 Max)"


def test_heart_rate_zone_classification():
    """Verify standard 5-zone HR formula against reference values for 190 bpm max HR."""
    max_hr = 190

    # Zone 1 (Recovery, < 60% = < 114 bpm)
    z, name = get_simulated_heart_rate_zone(105, max_hr)
    assert z == 1
    assert "Recovery" in name

    # Zone 2 (Aerobic Base, 60% to 70% = 114 to 133 bpm)
    z, name = get_simulated_heart_rate_zone(125, max_hr)
    assert z == 2
    assert "Aerobic" in name

    # Zone 3 (Tempo, 70% to 80% = 133 to 152 bpm)
    z, name = get_simulated_heart_rate_zone(142, max_hr)
    assert z == 3
    assert "Tempo" in name

    # Zone 4 (Threshold, 80% to 90% = 152 to 171 bpm)
    z, name = get_simulated_heart_rate_zone(162, max_hr)
    assert z == 4
    assert "Threshold" in name

    # Zone 5 (VO2 Max, >= 90% = >= 171 bpm)
    z, name = get_simulated_heart_rate_zone(178, max_hr)
    assert z == 5
    assert "VO2 Max" in name


def simulate_gatt_0x2a37_parser(packet_bytes):
    """Python reference simulator mirroring parseHeartRateMeasurement(dataView)."""
    flags = packet_bytes[0]
    is_16_bit = bool(flags & 0x01)
    if is_16_bit:
        bpm = packet_bytes[1] | (packet_bytes[2] << 8)
    else:
        bpm = packet_bytes[1]
    return bpm


def test_bluetooth_gatt_heart_rate_packet_decoding():
    """Verify Bluetooth SIG GATT 0x2A37 format parsing for both UINT8 and UINT16 payloads."""
    # UINT8 format (flags bit 0 = 0): flags=0x00, bpm=142
    uint8_packet = bytearray([0x00, 142])
    assert simulate_gatt_0x2a37_parser(uint8_packet) == 142

    # UINT16 format (flags bit 0 = 1): flags=0x01, bpm=175 (0x00AF in little-endian = [0xAF, 0x00])
    uint16_packet = bytearray([0x01, 0xAF, 0x00])
    assert simulate_gatt_0x2a37_parser(uint16_packet) == 175
