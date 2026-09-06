import asyncio
import os
import time
import subprocess
from playwright.async_api import async_playwright

async def run():
    # Start flask server
    env = os.environ.copy()
    env["FLASK_APP"] = "app.py"
    process = subprocess.Popen(["flask", "run", "--port", "5000"], env=env)
    time.sleep(3) # Wait for server to start
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Register user
            await page.goto("http://localhost:5000/register")
            await page.fill("input[name=username]", "goals_tester2")
            await page.fill("input[name=pin]", "1234")
            await page.click("button[type=submit]")
            await page.wait_for_timeout(1000)
            
            # Go to dashboard, wait for it to load
            await page.goto("http://localhost:5000/dashboard")
            await page.wait_for_timeout(1000)
            
            # Click Achievements tab
            await page.evaluate("switchTab('achievements', null)")
            await page.wait_for_timeout(500)
            
            # Click Personal Goals subtab
            await page.evaluate("switchAchievementTab('personalGoals')")
            await page.wait_for_timeout(500)
            
            # 1. Screenshot of Preset Goals List
            await page.screenshot(path="scratch/1_preset_goals.png")
            
            # 2. Open custom form and submit absurd goal for rejection
            await page.evaluate("showCreateCustomGoalForm()")
            await page.select_option("#goalTargetDistance", "42")
            
            # Set target date to tomorrow
            tomorrow = await page.evaluate("(() => { let d = new Date(); d.setDate(d.getDate() + 1); return d.toISOString().split('T')[0]; })()")
            await page.fill("#goalTargetDate", tomorrow)
            await page.click("button:has-text('Check Feasibility')")
            await page.wait_for_timeout(1000)
            
            await page.screenshot(path="scratch/2_rejected_goal.png")
            
            # 3. Feasible goal's generated calendar
            # Click 'Use suggested date instead'
            await page.click("#btnUseSuggestedDate")
            await page.wait_for_timeout(500)
            await page.click("button:has-text('Check Feasibility')")
            await page.wait_for_timeout(1000)
            
            await page.screenshot(path="scratch/3_feasible_goal_calendar.png")
            
            # 4. Completed goal's celebration state
            # To simulate completion, we can log a run manually via JS fetch
            today = await page.evaluate("(() => { let d = new Date(); return d.toISOString().split('T')[0]; })()")
            await page.evaluate(f"""
            fetch('/add', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/x-www-form-urlencoded',
                }},
                body: new URLSearchParams({{
                    'date': '{today}',
                    'distance_km': '45',
                    'time_min': '240',
                    'run_type': 'long'
                }})
            }})
            """)
            await page.wait_for_timeout(1500)
            
            # Reload page to see completed goal
            await page.goto("http://localhost:5000/dashboard")
            await page.wait_for_timeout(1000)
            await page.evaluate("switchTab('achievements', null)")
            await page.wait_for_timeout(500)
            await page.evaluate("switchAchievementTab('personalGoals')")
            await page.wait_for_timeout(1000)
            
            await page.screenshot(path="scratch/4_completed_goal.png")
            
            await browser.close()
    finally:
        process.terminate()

if __name__ == "__main__":
    asyncio.run(run())
