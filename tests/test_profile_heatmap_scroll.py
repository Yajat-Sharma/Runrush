"""
The profile heatmap lists 365 days oldest -> newest in a horizontally
scrolling container. On narrow screens it used to open scrolled to the oldest
end, so the most recent days -- the ones people look for -- were off-screen and
the heatmap looked empty. It should open scrolled to the newest end.

Runs the real static/js/profile.js under Node with a stubbed DOM.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "js" / "profile_heatmap_scroll.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def test_heatmap_opens_scrolled_to_most_recent_days():
    out = subprocess.run(["node", str(SCRIPT)], capture_output=True, text=True, timeout=30, check=True)
    r = json.loads(out.stdout.strip().splitlines()[-1])
    assert r["cells"] == 365
    assert r["scrollLeft"] == r["scrollWidth"]
