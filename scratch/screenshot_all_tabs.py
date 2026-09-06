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
        
        # 1. Runs Tab
        page.click("a.tab-nav-item[data-tab='runs']")
        time.sleep(1)
        page.screenshot(path=os.path.join(SCRATCH_DIR, "tab_runs.png"), full_page=True)
        print("Runs screenshot saved.")
        
        # 2. Leaderboard Tab
        page.click("a.tab-nav-item[data-tab='leaderboard']")
        time.sleep(1)
        page.screenshot(path=os.path.join(SCRATCH_DIR, "tab_leaderboard.png"), full_page=True)
        print("Leaderboard screenshot saved.")
        
        # 3. Analytics Tab
        page.click("a.tab-nav-item[data-tab='analytics']")
        time.sleep(1)
        page.screenshot(path=os.path.join(SCRATCH_DIR, "tab_analytics.png"), full_page=True)
        print("Analytics screenshot saved.")

        # 4. Achievements Tab
        page.click("a.tab-nav-item[data-tab='achievements']")
        time.sleep(1)
        page.screenshot(path=os.path.join(SCRATCH_DIR, "tab_achievements.png"), full_page=True)
        print("Achievements screenshot saved.")
        
        browser.close()

if __name__ == '__main__':
    run()
