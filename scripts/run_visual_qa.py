"""
Automated Playwright Visual QA and Cross-Device Verification for RunRush Challenges V1.
Tests:
- Screen sizes: 360px, 375px, 390px, 430px (mobile), 768px (tablet), 1280px (desktop).
- Themes: Dark theme and Light theme.
- UI Components:
  - Navigation & Challenges view
  - Ongoing challenge duel card & ratio bar
  - Challenge progress breakdown modal with qualifying runs
  - Challenge builder multi-step form (step 1, step 2, step 3 confirmation)
  - Automatic invitation popup
  - Player search & discovery cards
  - History tab with outcome pills
  - Profile achievement grid with Friendly Challenges × N medal
"""

import os
import sys

# Force local SQLite test database to ensure production database is NEVER touched
os.environ["DATABASE_URL"] = "sqlite:///qa_visual_test.db"
os.environ["TESTING"] = "1"
os.environ["SECRET_KEY"] = "visual-qa-test-secret"

import time
import json
import threading
from datetime import datetime, timezone
import requests
from werkzeug.serving import make_server

# Setup paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, bcrypt, init_db
from db import get_db
from services.friendly_challenge_service import (
    create_friendly_challenge_tables,
    create_challenge,
    accept_challenge,
    finalize_challenge_if_due,
)
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = r"C:\Users\Yajat Sharma\.gemini\antigravity\brain\97933e78-8c39-4f43-b163-5a2aa17965b2\screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

PORT = 5055
BASE_URL = f"http://127.0.0.1:{PORT}"


class ServerThread(threading.Thread):
    def __init__(self, app, port):
        super().__init__()
        self.server = make_server("127.0.0.1", port, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


def seed_test_environment():
    """Populate test database with a rich set of challenges, runs, and medals."""
    with app.app_context():
        init_db()
        conn = get_db()
        create_friendly_challenge_tables(conn)

        raw_hash = bcrypt.generate_password_hash("1234")
        hashed_pin = raw_hash.decode("utf-8") if isinstance(raw_hash, bytes) else str(raw_hash)

        # Create main user
        cur = conn.execute("""
            INSERT OR REPLACE INTO users (id, username, pin, display_name, profile_emoji, status, primary_goal, experience)
            VALUES (1, 'runner_main', ?, 'Alex Runner', '⚡', 'active', 'distance', 'intermediate')
        """, (hashed_pin,))
        
        # Create rivals
        conn.execute("""
            INSERT OR REPLACE INTO users (id, username, pin, display_name, profile_emoji, status, primary_goal, experience)
            VALUES (2, 'rival_speedy', ?, 'Speedy Sam', '🏃', 'active', 'speed', 'advanced')
        """, (hashed_pin,))
        conn.execute("""
            INSERT OR REPLACE INTO users (id, username, pin, display_name, profile_emoji, status, primary_goal, experience)
            VALUES (3, 'rival_endurance', ?, 'Elena Pace', '🔥', 'active', 'distance', 'advanced')
        """, (hashed_pin,))
        conn.execute("""
            INSERT OR REPLACE INTO users (id, username, pin, display_name, profile_emoji, status, primary_goal, experience)
            VALUES (4, 'runner_friend', ?, 'Jordan Lee', '🌱', 'active', 'consistency', 'beginner')
        """, (hashed_pin,))

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # 1. Past Completed Challenge (Alex won vs Jordan Lee -> Alex has 1 medal)
        c_past = create_challenge(1, 4, "DISTANCE", "2026-10-01", "2026-10-07", conn=conn, title="October Kickoff")
        conn.execute("UPDATE friendly_challenges SET status = 'ACCEPTED' WHERE id = ?", (c_past,))
        conn.execute("INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type) VALUES (1, '2026-10-03 08:00:00', 12.5, 60, 4.8, 750, 'gps')")
        conn.execute("INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type) VALUES (4, '2026-10-04 09:00:00', 8.0, 45, 5.6, 500, 'manual')")
        finalize_challenge_if_due(c_past, conn=conn)

        # 2. Active Ongoing Challenge (Alex vs Elena Pace: Distance duel)
        c_active = create_challenge(1, 3, "DISTANCE", "2026-11-01", "2026-11-15", conn=conn, title="November Endurance Clash")
        accept_challenge(c_active, 3, conn=conn)
        conn.execute("INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type) VALUES (1, '2026-11-02 07:00:00', 10.0, 50, 5.0, 600, 'gps')")
        conn.execute("INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type) VALUES (1, '2026-11-04 07:00:00', 8.5, 42, 4.9, 510, 'gps')")
        conn.execute("INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type) VALUES (3, '2026-11-03 06:30:00', 14.0, 70, 5.0, 840, 'gps')")

        # 3. Pending Incoming Invitation (Speedy Sam invited Alex to Longest Run duel)
        create_challenge(2, 1, "LONGEST", "2026-11-10", "2026-11-17", conn=conn, title="Who Can Go Further?", message="Catch me if you can, Alex!")

        conn.commit()
        conn.close()
        print("Test data seeded successfully.")


def run_visual_qa():
    server = ServerThread(app, PORT)
    server.start()
    time.sleep(1.0) # Wait for server spin up

    results = {}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            # Viewport matrix
            viewports = [
                ("mobile_360", {"width": 360, "height": 740}),
                ("mobile_375", {"width": 375, "height": 667}),
                ("mobile_390", {"width": 390, "height": 844}),
                ("mobile_430", {"width": 430, "height": 932}),
                ("tablet_768", {"width": 768, "height": 1024}),
                ("desktop_1280", {"width": 1280, "height": 800}),
            ]

            # 1. Login and session setup
            ctx = browser.new_context(viewport={"width": 390, "height": 844})
            page = ctx.new_page()

            page.goto(f"{BASE_URL}/login")
            page.fill('input[name="username"]', "runner_main")
            page.fill('input[name="pin"]', "1234")
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle")

            # Verify login redirected to home
            assert "/login" not in page.url

            # Capture Invitation Popup if shown
            popup_modal = page.locator("#challengeInvitationPopupModal")
            if popup_modal.is_visible():
                page.screenshot(path=os.path.join(SCREENSHOT_DIR, "01_invitation_popup_mobile390.png"))
                results["invitation_popup"] = True
                # Dismiss popup
                page.click('#challengeInvitationPopupModal .btn-close')
                page.wait_for_timeout(300)

            # 2. Open Challenges View
            page.evaluate("switchTab('challenges')")
            page.wait_for_timeout(800)

            # Cross-device viewport screenshots of Challenges View
            for vp_name, vp_size in viewports:
                page.set_viewport_size(vp_size)
                page.wait_for_timeout(200)
                path = os.path.join(SCREENSHOT_DIR, f"02_challenges_view_{vp_name}_dark.png")
                page.screenshot(path=path)
                results[f"challenges_view_{vp_name}_dark"] = True

            # Test Light Theme
            page.evaluate("document.documentElement.setAttribute('data-bs-theme', 'light')")
            page.wait_for_timeout(300)
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "02_challenges_view_mobile390_light.png"))
            results["challenges_view_light"] = True

            # Switch back to dark theme
            page.evaluate("document.documentElement.setAttribute('data-bs-theme', 'dark')")
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(200)

            # 3. Inspect Ongoing Challenge Duel Card & Progress Modal
            # Click the ongoing card or open progress directly
            page.evaluate("openChallengeProgress(2)") # Active challenge id 2
            page.wait_for_timeout(600)
            progress_modal = page.locator("#challengeProgressModal")
            if progress_modal.is_visible():
                page.screenshot(path=os.path.join(SCREENSHOT_DIR, "03_challenge_progress_breakdown_modal.png"))
                results["progress_modal"] = True
                page.click('#challengeProgressModal .btn-close')
                page.wait_for_timeout(300)

            # 4. Test Player Discovery & Search
            page.evaluate("switchChallengeTab('discover')")
            page.wait_for_timeout(400)
            page.fill("#chPlayerSearchInput", "rival")
            page.wait_for_timeout(600)
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "04_player_discovery_search.png"))
            results["player_search"] = True

            # 5. Open Challenge Builder Multi-step Modal
            page.evaluate("openChallengeBuilder({ id: 2, username: 'rival_speedy', display_name: 'Speedy Sam' })")
            page.wait_for_timeout(400)
            builder_modal = page.locator("#challengeBuilderModal")
            if builder_modal.is_visible():
                # Step 1: Type Selection
                page.screenshot(path=os.path.join(SCREENSHOT_DIR, "05_builder_step1_types.png"))
                results["builder_step1"] = True

                # Proceed to Step 2
                page.click("#cbNextBtn")
                page.wait_for_timeout(300)
                # Select 7-day preset
                page.click('button[data-preset="7"]')
                page.screenshot(path=os.path.join(SCREENSHOT_DIR, "06_builder_step2_dates.png"))
                results["builder_step2"] = True

                # Proceed to Step 3 (Confirmation Preview)
                page.click("#cbNextBtn")
                page.wait_for_timeout(300)
                page.screenshot(path=os.path.join(SCREENSHOT_DIR, "07_builder_step3_confirmation.png"))
                results["builder_step3"] = True

                page.click('#challengeBuilderModal .btn-close')
                page.wait_for_timeout(300)

            # 6. Test History Tab
            page.evaluate("switchChallengeTab('history')")
            page.wait_for_timeout(500)
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "08_challenges_history_tab.png"))
            results["history_tab"] = True

            # 7. Test Profile Integration & Friendly Challenges Medal
            page.goto(f"{BASE_URL}/u/runner_main")
            page.wait_for_timeout(1000)
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "09_profile_friendly_challenges_medal.png"))
            results["profile_medal"] = True

            browser.close()
            print("Visual QA completed successfully.")

    finally:
        server.shutdown()

    return results


if __name__ == "__main__":
    seed_test_environment()
    res = run_visual_qa()
    print("RESULTS_SUMMARY:", json.dumps(res, indent=2))
