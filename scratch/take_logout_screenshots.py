import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Desktop context
        desktop_context = await browser.new_context(
            viewport={'width': 1280, 'height': 800}
        )
        page = await desktop_context.new_page()
        
        # 1. Register new user
        await page.goto("http://localhost:5000/register")
        await page.fill('input[name="username"]', "testuser_screenshot4")
        await page.fill('input[name="pin"]', "1234")
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(3000)
        
        # Take desktop sidebar screenshot
        await page.screenshot(path="C:/Users/Yajat Sharma/.gemini/antigravity/brain/392e3157-7015-441e-abc7-d5c6f835017f/logout_desktop_sidebar.png")
        print("Desktop sidebar screenshot saved.")
        
        # Go to Settings
        await page.goto("http://localhost:5000/settings")
        await page.wait_for_timeout(2000)
        
        # Click Danger Zone tab to show it
        await page.click('a.nav-item[data-target="danger"]')
        await page.wait_for_timeout(500)
        
        # Take settings screenshot
        await page.screenshot(path="C:/Users/Yajat Sharma/.gemini/antigravity/brain/392e3157-7015-441e-abc7-d5c6f835017f/logout_settings.png")
        print("Settings screenshot saved.")
        
        # Logout via Settings to test it
        await page.click('#sec-danger a[href="/logout"]')
        await page.wait_for_url("http://localhost:5000/login")
        print("Settings logout test successful.")
        
        # Mobile context
        mobile_context = await browser.new_context(
            viewport={'width': 375, 'height': 812},
            is_mobile=True,
            has_touch=True
        )
        mobile_page = await mobile_context.new_page()
        
        # Login again
        await mobile_page.goto("http://localhost:5000/login")
        await mobile_page.fill('input[name="username"]', "testuser_screenshot4")
        await mobile_page.fill('input[name="pin"]', "1234")
        await mobile_page.click('button[type="submit"]')
        await mobile_page.wait_for_timeout(3000)
        
        # Wait for render
        await mobile_page.wait_for_timeout(2000)
        
        # Open mobile menu
        await mobile_page.click('button[data-bs-target="#appMenu"]')
        await mobile_page.wait_for_timeout(1000)
        
        # Take mobile menu screenshot
        await mobile_page.screenshot(path="C:/Users/Yajat Sharma/.gemini/antigravity/brain/392e3157-7015-441e-abc7-d5c6f835017f/logout_mobile_menu.png")
        print("Mobile menu screenshot saved.")
        
        # Logout via mobile menu to test it
        await mobile_page.click('#appMenu a[href="/logout"]')
        await mobile_page.wait_for_url("http://localhost:5000/login")
        print("Mobile menu logout test successful.")
        
        # Desktop Sidebar Logout Test (Login one more time)
        await page.goto("http://localhost:5000/login")
        await page.fill('input[name="username"]', "testuser_screenshot4")
        await page.fill('input[name="pin"]', "1234")
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(3000)
        await page.wait_for_timeout(1000)
        
        await page.click('.sidebar-footer a[href="/logout"]')
        await page.wait_for_url("http://localhost:5000/login")
        print("Desktop sidebar logout test successful.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
