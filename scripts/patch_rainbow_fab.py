"""Patch index.html: replace 2 FAB buttons with rainbow expandable action FAB."""
import os

HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates', 'index.html')

with open(HTML, 'r', encoding='utf-8', newline='') as f:
    src = f.read()

NL = '\r\n' if '\r\n' in src else '\n'

# 1. switchTab
old_switch = NL.join([
    "      // Show the voice quick-log FAB and Start Run FAB only on the home tab",
    "      const voiceBtn = document.getElementById('voiceQuickLogBtn');",
    "      if (voiceBtn) voiceBtn.style.display = (tabId === 'home') ? '' : 'none';",
    "      const startRunBtn = document.getElementById('startRunBtn');",
    "      if (startRunBtn) startRunBtn.style.display = (tabId === 'home') ? '' : 'none';",
    "    }"
])
new_switch = NL.join([
    "      // Show the rainbow quick-action FAB only on the home tab",
    "      const quickFab = document.getElementById('quickActionsFab');",
    "      if (quickFab) {",
    "        quickFab.style.display = (tabId === 'home') ? '' : 'none';",
    "        if (tabId !== 'home' && typeof closeQuickActions === 'function') closeQuickActions();",
    "      }",
    "    }"
])

if old_switch in src:
    src = src.replace(old_switch, new_switch, 1)
    print("OK: switchTab patched for quickActionsFab")
else:
    print("WARN: switchTab target not found")

# 2. Replace the two FAB buttons with {% include "partials/_quick_actions_fab.html" %}
old_btns = NL.join([
    '<button id="voiceQuickLogBtn" onclick="openVoiceQuickLog()" class="btn btn-dark btn-lg rounded-circle shadow position-fixed" style="bottom:90px;right:20px;z-index:1050;width:56px;height:56px;" aria-label="Voice quick log" title="Voice quick log"><i class="fa-solid fa-microphone"></i></button>',
    '',
    '<!-- Start Run FAB — Live GPS Tracker -->',
    '<button id="startRunBtn" onclick="openLiveRunTracker()" class="btn btn-success btn-lg rounded-circle shadow position-fixed" style="bottom:160px;right:20px;z-index:1050;width:56px;height:56px;" aria-label="Start live run" title="Start live run"><i class="fa-solid fa-play"></i></button>'
])
new_btns = '{% include "partials/_quick_actions_fab.html" %}'

if old_btns in src:
    src = src.replace(old_btns, new_btns, 1)
    print("OK: buttons replaced with rainbow FAB partial")
else:
    print("WARN: old_btns target not found")

with open(HTML, 'w', encoding='utf-8', newline='') as f:
    f.write(src)

print("Finished updating index.html")
