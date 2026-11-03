"""Patch index.html: add Leaflet CDN, Start Run FAB, switchTab toggle, and includes."""
import os

HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates', 'index.html')

with open(HTML, 'r', encoding='utf-8', newline='') as f:
    src = f.read()

# ── 1. Add Leaflet CSS + JS in <head> after Bootstrap link ────────────────────
old_bs = '  <!-- html2canvas for Share Run Card -->'
new_bs = (
    '  <!-- Leaflet.js — free interactive maps (OpenStreetMap, no API key) -->\n'
    '  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>\n'
    '  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV/XN/WLcE=" crossorigin=""></script>\n'
    '\n'
    '  <!-- html2canvas for Share Run Card -->'
)
if old_bs in src:
    src = src.replace(old_bs, new_bs, 1)
    print('OK: Leaflet CDN added')
else:
    print('WARN: Bootstrap marker not found for Leaflet insert')

NL = '\r\n'  # file uses CRLF

# ── 2. switchTab — add Start Run FAB toggle ───────────────────────────────────
old_switch = NL.join([
    "      // Show the voice quick-log FAB only on the home tab",
    "      const voiceBtn = document.getElementById('voiceQuickLogBtn');",
    "      if (voiceBtn) voiceBtn.style.display = (tabId === 'home') ? '' : 'none';",
    "    }"
])
new_switch = NL.join([
    "      // Show the voice quick-log FAB and Start Run FAB only on the home tab",
    "      const voiceBtn = document.getElementById('voiceQuickLogBtn');",
    "      if (voiceBtn) voiceBtn.style.display = (tabId === 'home') ? '' : 'none';",
    "      const startRunBtn = document.getElementById('startRunBtn');",
    "      if (startRunBtn) startRunBtn.style.display = (tabId === 'home') ? '' : 'none';",
    "    }"
])
if old_switch in src:
    src = src.replace(old_switch, new_switch, 1)
    print('OK: switchTab patched for startRunBtn')
else:
    print('WARN: switchTab target not found')

# ── 3. Add Start Run FAB button + includes before </body> ─────────────────────
old_bottom = NL.join([
    '<button id="voiceQuickLogBtn" onclick="openVoiceQuickLog()" class="btn btn-dark btn-lg rounded-circle shadow position-fixed" style="bottom:90px;right:20px;z-index:1050;width:56px;height:56px;" aria-label="Voice quick log" title="Voice quick log"><i class="fa-solid fa-microphone"></i></button>',
    '{% include "partials/_voice_modal.html" %}',
    '<script src="{{ url_for(\'static\', filename=\'js/voice_quick_log.js\', v=\'voice-v3\') }}"></script>',
    '<script src="{{ url_for(\'static\', filename=\'js/monthly-report.js\', v=\'report-v1\') }}"></script>',
    '</body>'
])
new_bottom = NL.join([
    '<button id="voiceQuickLogBtn" onclick="openVoiceQuickLog()" class="btn btn-dark btn-lg rounded-circle shadow position-fixed" style="bottom:90px;right:20px;z-index:1050;width:56px;height:56px;" aria-label="Voice quick log" title="Voice quick log"><i class="fa-solid fa-microphone"></i></button>',
    '',
    '<!-- Start Run FAB — Live GPS Tracker -->',
    '<button id="startRunBtn" onclick="openLiveRunTracker()" class="btn btn-success btn-lg rounded-circle shadow position-fixed" style="bottom:160px;right:20px;z-index:1050;width:56px;height:56px;" aria-label="Start live run" title="Start live run"><i class="fa-solid fa-play"></i></button>',
    '',
    '{% include "partials/_voice_modal.html" %}',
    '{% include "partials/_live_run_modal.html" %}',
    '{% include "partials/_route_view_modal.html" %}',
    '<script src="{{ url_for(\'static\', filename=\'js/voice_quick_log.js\', v=\'voice-v3\') }}"></script>',
    '<script src="{{ url_for(\'static\', filename=\'js/monthly-report.js\', v=\'report-v1\') }}"></script>',
    '<script src="{{ url_for(\'static\', filename=\'js/live_run_tracker.js\', v=\'lrt-v1\') }}"></script>',
    '</body>'
])
if old_bottom in src:
    src = src.replace(old_bottom, new_bottom, 1)
    print('OK: Start Run FAB + includes added')
else:
    print('WARN: bottom target not found')

with open(HTML, 'w', encoding='utf-8', newline='') as f:
    f.write(src)
print('index.html saved.')
