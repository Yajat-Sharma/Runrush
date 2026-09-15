import asyncio
from playwright.async_api import async_playwright
import os

async def take_screenshots():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 720})
        
        # Login
        await page.goto("http://localhost:5000/login")
        await page.fill("input[name=username]", "simulation_user")
        await page.fill("input[name=pin]", "0000")
        await page.click("button[type=submit]")
        await page.wait_for_timeout(1000)
        
        # Go to dashboard
        await page.goto("http://localhost:5000/dashboard")
        await page.wait_for_timeout(2000)
        
        await page.screenshot(path="scratch/dashboard_widget.png")
        
        # Click Achievements tab via JS to bypass locator issues
        await page.evaluate("""
            document.querySelectorAll('[id$="View"]').forEach(v => v.style.display = 'none');
            document.getElementById('achievementsView').style.display = 'block';
            switchAchievementTab('personalGoals');
        """)
        await page.wait_for_timeout(2000)
        
        # wait for JS to load the goal
        await page.wait_for_selector('div[data-bs-toggle="collapse"]', timeout=5000)
        await page.wait_for_timeout(1000)
        
        # Screenshot collapsed calendar
        await page.screenshot(path="scratch/collapsed_calendar.png")
        
        # Expand calendar
        await page.evaluate("""
            let btn = document.querySelector('div[data-bs-toggle="collapse"]');
            if (btn) btn.click();
        """)
        await page.wait_for_timeout(1000)
        
        # Screenshot expanded calendar (at-risk state since we logged a shortfall)
        await page.screenshot(path="scratch/expanded_calendar_at_risk.png")
        
        await browser.close()

if __name__ == "__main__":
    if not os.path.exists('scratch'):
        os.makedirs('scratch')
    asyncio.run(take_screenshots())
