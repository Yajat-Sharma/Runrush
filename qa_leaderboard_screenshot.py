"""
Minimal screenshot script: logs in as existing qa_runner1,
navigates to leaderboard tab, takes screenshot.
"""
import asyncio, os
from playwright.async_api import async_playwright
from datetime import date

BASE = "http://127.0.0.1:5000"
OUT_DIR = os.path.join(os.path.dirname(__file__), "qa_screenshots")
os.makedirs(OUT_DIR, exist_ok=True)
TODAY = date.today().isoformat()

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # --- seed qa_runner1 (5km qualified) ---
        ctx = await browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        page = await ctx.new_page()

        # Try login; if fails, register first
        await page.goto(f"{BASE}/login")
        await page.fill('input[name="username"]', "qa_runner1")
        await page.fill('input[name="pin"]', "9999")
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(1000)

        if "/login" in page.url:
            # Need to register
            await page.goto(f"{BASE}/register")
            await page.fill('input[name="username"]', "qa_runner1")
            await page.fill('input[name="pin"]', "9999")
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(800)
            await page.goto(f"{BASE}/login")
            await page.fill('input[name="username"]', "qa_runner1")
            await page.fill('input[name="pin"]', "9999")
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(800)

        print(f"runner1 url: {page.url}")

        # Post a 5km run
        status = await page.evaluate("""async (today) => {
            const fd = new FormData();
            fd.append('date', today); fd.append('distance', '5.0');
            fd.append('time', '30'); fd.append('run_type', 'easy');
            const r = await fetch('/add', {method:'POST', body: new URLSearchParams({date:today,distance:'5.0',time:'30',run_type:'easy'})});
            return r.status;
        }""", TODAY)
        print(f"runner1 add status: {status}")
        await ctx.close()

        # --- seed qa_runner2 (0.5km unqualified) ---
        ctx2 = await browser.new_context(viewport={"width": 390, "height": 844})
        page2 = await ctx2.new_page()

        await page2.goto(f"{BASE}/login")
        await page2.fill('input[name="username"]', "qa_runner2")
        await page2.fill('input[name="pin"]', "9999")
        await page2.click('button[type="submit"]')
        await page2.wait_for_timeout(1000)

        if "/login" in page2.url:
            await page2.goto(f"{BASE}/register")
            await page2.fill('input[name="username"]', "qa_runner2")
            await page2.fill('input[name="pin"]', "9999")
            await page2.click('button[type="submit"]')
            await page2.wait_for_timeout(800)
            await page2.goto(f"{BASE}/login")
            await page2.fill('input[name="username"]', "qa_runner2")
            await page2.fill('input[name="pin"]', "9999")
            await page2.click('button[type="submit"]')
            await page2.wait_for_timeout(800)

        print(f"runner2 url: {page2.url}")

        status2 = await page2.evaluate("""async (today) => {
            const r = await fetch('/add', {method:'POST', body: new URLSearchParams({date:today,distance:'0.5',time:'5',run_type:'easy'})});
            return r.status;
        }""", TODAY)
        print(f"runner2 add status: {status2}")
        await ctx2.close()

        # --- final screenshot as runner1 ---
        ctx3 = await browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        page3 = await ctx3.new_page()

        await page3.goto(f"{BASE}/login")
        await page3.fill('input[name="username"]', "qa_runner1")
        await page3.fill('input[name="pin"]', "9999")
        await page3.click('button[type="submit"]')
        await page3.wait_for_load_state("networkidle")
        await page3.wait_for_timeout(1000)

        # Click leaderboard tab
        await page3.evaluate("""() => {
            document.querySelectorAll('[data-tab="leaderboard"]').forEach(t => t.click());
        }""")
        await page3.wait_for_timeout(1500)

        for w, label in [(375, "375px"), (390, "390px"), (430, "430px")]:
            await page3.set_viewport_size({"width": w, "height": 844})
            await page3.wait_for_timeout(400)
            out = os.path.join(OUT_DIR, f"lb_final_{label}.png")
            await page3.screenshot(path=out, full_page=False)
            print(f"Saved: {out}")

        await ctx3.close()
        await browser.close()
        print("All done.")

asyncio.run(run())
