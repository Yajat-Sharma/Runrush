"""
Frontend regression for the Public Profile "Pace Pet Collection" section.

/api/pet-collection returns a catalog: one entry per pet type, with
status 'owned' | 'unlocked' | 'locked'. Only owned entries carry pet_name /
level / level_name / is_active. profile.js used to render every entry as an
owned pet, producing "undefined" names and "(Lvl undefined)", and its
"no pets -> hide section" guard (collection.length === 0) could never fire.

Runs the real static/js/profile.js under Node with a stubbed DOM.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "js" / "profile_pet_render.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

OWNED = {
    "pet_type": "dog", "status": "owned", "is_active": True, "collection_id": 1,
    "pet_name": "Speedy", "level": 2, "level_name": "Pup",
}
UNLOCKED = {"pet_type": "bird", "status": "unlocked", "definition": {}}
LOCKED = {"pet_type": "dragon", "status": "locked", "definition": {}, "unlock_distance": 50}


def render(collection):
    payload = {"status": "success", "collection": collection, "total_lifetime_km": 0}
    out = subprocess.run(
        ["node", str(SCRIPT), json.dumps(payload)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_owned_pet_name_is_rendered_and_unowned_entries_are_skipped():
    r = render([OWNED, UNLOCKED, LOCKED])
    assert r["sectionDisplay"] == "block"
    assert "Speedy" in r["html"]
    assert "Pup (Lvl 2)" in r["html"]
    assert "undefined" not in r["html"]
    assert r["html"].count("stat-card") == 1  # one card, only for the owned pet


def test_section_hidden_when_user_owns_no_pets():
    r = render([UNLOCKED, LOCKED, {"pet_type": "x", "status": "locked"}])
    assert r["sectionDisplay"] == "none"
    assert "undefined" not in r["html"]


def test_section_hidden_when_collection_empty():
    r = render([])
    assert r["sectionDisplay"] == "none"
