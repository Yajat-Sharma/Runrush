"""Apply migration 015: Add friendly_challenges, challenge_participants, challenge_awards, challenge_activity."""
from pathlib import Path
import sys, os

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app
from services.friendly_challenge_service import create_friendly_challenge_tables

def apply():
    with app.app_context():
        create_friendly_challenge_tables()
        print("Migration 015 applied successfully.")

if __name__ == "__main__":
    apply()
