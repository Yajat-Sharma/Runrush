import asyncio
import os
from playwright.async_api import async_playwright

async def capture_drawer_screenshots():
    os.makedirs("scratch", exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        
        # 1. Desktop Check (1440px)
        context_desktop = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context_desktop.new_page()
        await page.goto("http://localhost:5000/login")
        await page.fill("input[name=username]", "simulation_user")
        await page.fill("input[name=pin]", "0000")
        await page.click("button[type=submit]")
        await page.wait_for_url("**/dashboard")
        await page.evaluate("""
            document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
            document.body.classList.remove('modal-open');
            document.body.style = '';
        """)
        await page.wait_for_timeout(500)
        await page.screenshot(path="scratch/desktop_sidebar_untouched.png")
        await context_desktop.close()
        
        # Mobile views
        for width in [375, 390, 430]:
            # For 375, typically height is 812
            # For 390, typically 844
            # For 430, typically 932
            height = 812 if width == 375 else (844 if width == 390 else 932)
            context = await browser.new_context(viewport={"width": width, "height": height})
            page = await context.new_page()
            
            await page.goto("http://localhost:5000/login")
            await page.fill("input[name=username]", "simulation_user")
            await page.fill("input[name=pin]", "0000")
            await page.click("button[type=submit]")
            await page.wait_for_url("**/dashboard")
            
            await page.evaluate("""
                document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
                document.body.classList.remove('modal-open');
                document.body.style = '';
            """)
            await page.wait_for_timeout(500)
            
            # Open drawer
            await page.click('button[data-bs-target="#appMenu"]', force=True)
            await page.wait_for_timeout(500)
            
            await page.screenshot(path=f"scratch/drawer_{width}px.png")
            await context.close()
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_drawer_screenshots())
