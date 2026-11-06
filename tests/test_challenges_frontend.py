"""
Frontend integration tests for Friendly Challenges JS (runs Node.js VM).
"""

import json
import shutil
import subprocess
from pathlib import Path
import pytest

SCRIPT = Path(__file__).parent / "js" / "test_challenges_fe.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def test_challenges_frontend_controller():
    res = subprocess.run(["node", str(SCRIPT)], capture_output=True, text=True, timeout=10, check=True)
    out_lines = [l for l in res.stdout.strip().splitlines() if l.startswith("{")]
    assert len(out_lines) > 0, f"Expected JSON output from node script. Output: {res.stdout}"
    data = json.loads(out_lines[-1])
    assert data["success"] is True
    assert data["testsPassed"] >= 4
