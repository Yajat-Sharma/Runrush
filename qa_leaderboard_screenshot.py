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

        await page.goto(f"{BASE}/login")
        await page.fill('input[name="username"]', "qa_runner1")
        await page.fill('input[name="pin"]', "9999")
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(1000)

        if "/login" in page.url:
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

        status = await page.evaluate("""async (today) => {
            const fd = new FormData();
            fd.append('date', today); fd.append('distance', '5.0');
            fd.append('time', '30'); fd.append('run_type', 'easy');
            const r = await fetch('/add', {method:'POST', body: new URLSearchParams({date:today,distance:'5.0',time:'30',run_type:'easy'})});
            return r.status;
        }""", TODAY)
        print(f"runner1 add status: {status}")
        
        # Now visit the actual leaderboard page directly instead of the dashboard tab
        tabs = ['daily', 'weekly', 'monthly', 'all-time']
        for tab in tabs:
            await page.goto(f"{BASE}/leaderboard?tab={tab}")
            await page.wait_for_timeout(1000)
            
            for w, label in [(390, "390px")]:
                await page.set_viewport_size({"width": w, "height": 844})
                await page.wait_for_timeout(400)
                # Toggle light mode on one tab to show both themes
                if tab == 'monthly':
                    await page.evaluate("document.body.classList.add('light-theme')")
                out = os.path.join(OUT_DIR, f"lb_{tab}_{label}.png")
                await page.screenshot(path=out, full_page=False)
                print(f"Saved: {out}")
                
        await ctx.close()
        
        # Test empty state logic (login as new user, go to leaderboard)
        ctx2 = await browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        page2 = await ctx2.new_page()
        
        # Just go directly there (will redirect to login)
        await page2.goto(f"{BASE}/login")
        await page2.fill('input[name="username"]', "qa_runner_new123")
        await page2.fill('input[name="pin"]', "9999")
        await page2.click('button[type="submit"]')
        await page2.wait_for_timeout(1000)

        if "/login" in page2.url:
            await page2.goto(f"{BASE}/register")
            await page2.fill('input[name="username"]', "qa_runner_new123")
            await page2.fill('input[name="pin"]', "9999")
            await page2.click('button[type="submit"]')
            await page2.wait_for_timeout(800)
            await page2.goto(f"{BASE}/login")
            await page2.fill('input[name="username"]', "qa_runner_new123")
            await page2.fill('input[name="pin"]', "9999")
            await page2.click('button[type="submit"]')
            await page2.wait_for_timeout(800)
            
        await page2.goto(f"{BASE}/leaderboard?tab=daily")
        await page2.wait_for_timeout(1000)
        out = os.path.join(OUT_DIR, f"lb_empty_state_390px.png")
        await page2.screenshot(path=out, full_page=False)
        print(f"Saved: {out}")

        await ctx2.close()
        await browser.close()
        print("All done.")

asyncio.run(run())
