import asyncio
import os
from playwright.async_api import async_playwright

async def take_screenshots():
    os.makedirs("scratch", exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        
        # Desktop (1440px)
        context_desktop = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context_desktop.new_page()
        
        # Login
        await page.goto("http://localhost:5000/login")
        await page.fill("input[name=username]", "simulation_user")
        await page.fill("input[name=pin]", "0000")
        await page.click("button[type=submit]")
        await page.wait_for_url("**/dashboard")
        
        # Dismiss any modals
        await page.evaluate("""
            document.querySelectorAll('.modal').forEach(m => {
                try { if (window.bootstrap) { const bs = bootstrap.Modal.getInstance(m); if (bs) bs.hide(); } } catch(e) {}
            });
            document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
            document.body.classList.remove('modal-open');
            document.body.style = '';
        """)
        await page.wait_for_timeout(500)
        
        # First, ensure there is a run by inserting via API/form or we can just try to click Edit
        # Wait, the dashboard has Runs.
        # Click on the Runs tab using switchTab('runs') if on dashboard
        await page.evaluate("switchTab('runs', document.querySelector('a.tab-nav-item[data-tab=\"runs\"]'))")
        await page.wait_for_timeout(1000)
        
        # Find a run card and click Edit
        # The edit button has href="/edit/<id>"
        edit_link = await page.query_selector('a[href^="/edit/"]')
        
        if not edit_link:
            print("No run found to edit. Generating a dummy run via UI...")
            # Click quick start button
            await page.click('button[data-bs-target="#manualEntryModal"]', force=True)
            await page.wait_for_timeout(1000)
            
            # Fill manual entry modal
            await page.fill('#manualDate', '2026-09-11')
            await page.fill('#manualDistance', '5.0')
            await page.fill('#manualTime', '30.0')
            await page.click('#manualEntryModal button[type="submit"]', force=True)
            
            await page.wait_for_url("**/dashboard")
            await page.wait_for_timeout(1000)
            
            # Dismiss any modals (like adoption)
            await page.evaluate("""
                document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
                document.body.classList.remove('modal-open');
                document.body.style = '';
            """)
            
            # Re-switch to runs tab and find edit link
            await page.evaluate("switchTab('runs', document.querySelector('a.tab-nav-item[data-tab=\"runs\"]'))")
            await page.wait_for_timeout(1000)
            
            edit_link = await page.query_selector('a[href^="/edit/"]')
            
        if edit_link:
            await edit_link.click(force=True)
            await page.wait_for_url("**/edit/**")
            await page.wait_for_timeout(1000)
            
            # 1. Populated Edit Run screenshot (Desktop)
            await page.screenshot(path="scratch/edit_run_desktop_1440.png")
            
            # 2. Test pace preview update
            await page.fill("input[name=distance]", "10.0")
            await page.fill("input[name=time]", "60.0")
            await page.wait_for_timeout(500)
            
            # Save it
            await page.click("button[type=submit]", force=True)
            await page.wait_for_url("**/dashboard")
            print("Save changes verified.")
            
        await context_desktop.close()
        
        # Mobile (390px)
        context_mobile = await browser.new_context(viewport={"width": 390, "height": 844})
        page = await context_mobile.new_page()
        
        # Login
        await page.goto("http://localhost:5000/login")
        await page.fill("input[name=username]", "simulation_user")
        await page.fill("input[name=pin]", "0000")
        await page.click("button[type=submit]")
        await page.wait_for_url("**/dashboard")
        
        await page.evaluate("""
            document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
            document.body.classList.remove('modal-open');
        """)
        
        await page.evaluate("switchTab('runs', document.querySelector('a.tab-nav-item[data-tab=\"runs\"]'))")
        await page.wait_for_timeout(1000)
        
        edit_link = await page.query_selector('a[href^="/edit/"]')
        if edit_link:
            await edit_link.click(force=True)
            await page.wait_for_url("**/edit/**")
            await page.wait_for_timeout(1000)
            
            # 3. Mobile screenshot
            await page.screenshot(path="scratch/edit_run_mobile_390.png")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(take_screenshots())
