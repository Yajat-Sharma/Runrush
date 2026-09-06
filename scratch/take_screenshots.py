from playwright.sync_api import sync_playwright
import time
import os

SCRATCH_DIR = os.path.dirname(os.path.abspath(__file__))

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        
        # Login
        page.goto("http://127.0.0.1:5000/login")
        page.fill("input[name='username']", "dash_user_123")
        page.fill("input[name='pin']", "1234")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        # Go to Dashboard
        page.goto("http://127.0.0.1:5000/dashboard")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # --- Analytics Screenshots (Desktop, Tablet, Mobile) ---
        page.evaluate("switchTab('analytics')")
        time.sleep(2) # wait for animations/charts
        
        # Desktop
        page.set_viewport_size({"width": 1280, "height": 800})
        time.sleep(1)
        page.screenshot(path=os.path.join(SCRATCH_DIR, "analytics_desktop.png"), full_page=True)
        
        # Tablet
        page.set_viewport_size({"width": 768, "height": 1024})
        time.sleep(1)
        page.screenshot(path=os.path.join(SCRATCH_DIR, "analytics_tablet.png"), full_page=True)
        
        # Mobile
        page.set_viewport_size({"width": 375, "height": 812})
        time.sleep(1)
        page.screenshot(path=os.path.join(SCRATCH_DIR, "analytics_mobile.png"), full_page=True)
        
        # --- Other Tabs Audit (Desktop) ---
        page.set_viewport_size({"width": 1280, "height": 800})
        
        # Runs Tab
        page.evaluate("switchTab('runs')")
        time.sleep(1)
        page.screenshot(path=os.path.join(SCRATCH_DIR, "tab_runs.png"), full_page=True)
        
        # Leaderboard Tab
        page.evaluate("switchTab('leaderboard')")
        time.sleep(1)
        page.screenshot(path=os.path.join(SCRATCH_DIR, "tab_leaderboard.png"), full_page=True)
        
        # Achievements Tab
        page.evaluate("switchTab('achievements')")
        time.sleep(1)
        page.screenshot(path=os.path.join(SCRATCH_DIR, "tab_achievements.png"), full_page=True)
        
        browser.close()
        print("All screenshots generated successfully.")

if __name__ == '__main__':
    run()
