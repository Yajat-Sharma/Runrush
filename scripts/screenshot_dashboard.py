import asyncio
from playwright.async_api import async_playwright
import os

async def take_screenshots():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Test Desktop (1440px)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto("http://localhost:5000/login")
        await page.fill("input[name=username]", "simulation_user")
        await page.fill("input[name=pin]", "0000")
        await page.click("button[type=submit]")
        await page.wait_for_timeout(1000)
        
        await page.goto("http://localhost:5000/dashboard")
        await page.wait_for_timeout(1000)
        
        # Take a screenshot of the quick start section
        element = await page.query_selector('[data-widget="quick_start"]')
        if element:
            await element.screenshot(path="scratch/quickstart_desktop_1440.png")
        else:
            await page.screenshot(path="scratch/quickstart_desktop_1440.png", full_page=True)
        await page.close()
        
        # Test Mobile (390px)
        page = await browser.new_page(viewport={"width": 390, "height": 844})
        await page.goto("http://localhost:5000/dashboard")
        await page.wait_for_timeout(1000)
        
        element = await page.query_selector('[data-widget="quick_start"]')
        if element:
            await element.screenshot(path="scratch/quickstart_mobile_390.png")
        else:
            await page.screenshot(path="scratch/quickstart_mobile_390.png", full_page=True)
        await page.close()
        
        await browser.close()

if __name__ == "__main__":
    if not os.path.exists('scratch'):
        os.makedirs('scratch')
    asyncio.run(take_screenshots())
