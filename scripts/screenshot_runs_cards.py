import asyncio
from playwright.async_api import async_playwright
import os

async def take_screenshots():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Test Desktop (1440px)
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        await page.goto("http://localhost:5000/login")
        await page.fill("input[name=username]", "simulation_user")
        await page.fill("input[name=pin]", "0000")
        await page.click("button[type=submit]")
        await page.wait_for_timeout(2000)
        
        await page.goto("http://localhost:5000/dashboard")
        await page.wait_for_timeout(2000)
        
        # Dismiss any auto-opening modals (e.g. Pet Adoption)
        await page.evaluate("""
            document.querySelectorAll('.modal').forEach(m => {
                try { if (window.bootstrap) { const bs = bootstrap.Modal.getInstance(m); if (bs) bs.hide(); } } catch(e) {}
            });
            document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
            document.body.classList.remove('modal-open');
            document.body.style = '';
        """)
        await page.wait_for_timeout(500)
        
        # Switch to Runs tab
        await page.evaluate("document.querySelector('a.tab-nav-item[data-tab=\"runs\"]').click()")
        await page.wait_for_timeout(1000)
        
        await page.evaluate("window.scrollTo(0, 1000)")
        
        # Ensure Cards view is active by clicking the toggle button
        toggle_btn = await page.query_selector('#btnCardsView')
        if toggle_btn:
            await toggle_btn.click(force=True)
        await page.wait_for_timeout(1000)
        
        await page.screenshot(path="scratch/runs_cards_desktop.png")
        
        # Expand the first card if it exists
        has_cards = await page.evaluate("document.querySelector('.run-card-modern') !== null")
        if has_cards:
            await page.click('.run-card-modern', force=True)
            await page.wait_for_timeout(1000)
            await page.screenshot(path="scratch/runs_cards_desktop_expanded.png")
            # collapse it back
            await page.click('.run-card-modern', force=True)
            await page.wait_for_timeout(1000)
        else:
            await page.screenshot(path="scratch/runs_cards_desktop_empty.png")
            
        # Show List view
        list_btn = await page.query_selector('#btnListView')
        if list_btn:
            await list_btn.click(force=True)
        await page.wait_for_timeout(1000)
        await page.screenshot(path="scratch/runs_list_desktop.png")
        
        await page.close()
        
        # Test Mobile (390px)
        page = await browser.new_page(viewport={"width": 390, "height": 844})
        await page.goto("http://localhost:5000/login")
        await page.fill("input[name=username]", "simulation_user")
        await page.fill("input[name=pin]", "0000")
        await page.click("button[type=submit]")
        await page.wait_for_timeout(2000)
        
        await page.goto("http://localhost:5000/dashboard")
        await page.wait_for_timeout(2000)
        
        # Dismiss any auto-opening modals (e.g. Pet Adoption)
        await page.evaluate("""
            document.querySelectorAll('.modal').forEach(m => {
                try { if (window.bootstrap) { const bs = bootstrap.Modal.getInstance(m); if (bs) bs.hide(); } } catch(e) {}
            });
            document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
            document.body.classList.remove('modal-open');
            document.body.style = '';
        """)
        await page.wait_for_timeout(500)
        
        # Switch to Runs tab
        await page.evaluate("document.querySelector('a.tab-nav-item[data-tab=\"runs\"]').click()")
        await page.wait_for_timeout(1000)
        
        await page.evaluate("window.scrollTo(0, 1500)")
        
        mobile_toggle_btn = await page.query_selector('#btnCardsView')
        if mobile_toggle_btn:
            await mobile_toggle_btn.click(force=True)
        await page.wait_for_timeout(1000)
        
        await page.screenshot(path="scratch/runs_cards_mobile.png")
        
        # Expanded view
        if await page.evaluate("document.querySelector('.run-card-modern') !== null"):
            await page.click('.run-card-modern', force=True)
            await page.wait_for_timeout(1000)
            await page.screenshot(path="scratch/runs_cards_mobile_expanded.png")
            await page.click('.run-card-modern', force=True)
            await page.wait_for_timeout(1000)
            
        mobile_list_btn = await page.query_selector('#btnListView')
        if mobile_list_btn:
            await mobile_list_btn.click(force=True)
        await browser.close()

if __name__ == "__main__":
    if not os.path.exists('scratch'):
        os.makedirs('scratch')
    asyncio.run(take_screenshots())
