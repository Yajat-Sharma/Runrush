import asyncio
from playwright.async_api import async_playwright
import os

BASE = "http://127.0.0.1:5000"

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1200, "height": 800})
        page = await ctx.new_page()

        logs = []
        page.on("console", lambda msg: logs.append(f"CONSOLE: {msg.text}"))
        page.on("pageerror", lambda err: logs.append(f"ERROR: {err.message}"))

        # Log in
        await page.goto(f"{BASE}/login")
        await page.fill('input[name="username"]', "qa_runner1")
        await page.fill('input[name="pin"]', "9999")
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(1000)

        # Go to dashboard and click leaderboard tab
        await page.goto(f"{BASE}/dashboard")
        await page.wait_for_timeout(1000)

        await page.evaluate("""() => {
            const el = document.querySelector('[data-tab="leaderboard"]');
            if(el) el.click();
        }""")
        await page.wait_for_timeout(1000)

        out = os.path.join(os.path.dirname(__file__), "debug_dashboard.png")
        await page.screenshot(path=out)
        print("Screenshot saved to", out)
        
        # also print html of leaderboardView
        lb_html = await page.evaluate("""() => {
            const el = document.getElementById('leaderboardView');
            return el ? el.outerHTML : "NOT FOUND";
        }""")
        print("leaderboardView HTML length:", len(lb_html))

        for log in logs:
            print(log)

        await browser.close()

asyncio.run(run())
