import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # 1. Desktop Test (1920x1080)
        desktop_context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        desktop_page = await desktop_context.new_page()
        await desktop_page.goto("http://localhost:5000/login")
        await desktop_page.fill('input[name="username"]', "testuser_screenshot4")
        await desktop_page.fill('input[name="pin"]', "1234")
        await desktop_page.click('button[type="submit"]')
        await desktop_page.wait_for_timeout(3000)
        
        await desktop_page.screenshot(path="C:/Users/Yajat Sharma/.gemini/antigravity/brain/392e3157-7015-441e-abc7-d5c6f835017f/drawer_desktop.png")
        print("Desktop screenshot saved.")
        await desktop_context.close()
        
        # 2. Mobile Test (390x844 - iPhone 12/13/14)
        mobile_390_context = await browser.new_context(viewport={"width": 390, "height": 844})
        page_390 = await mobile_390_context.new_page()
        await page_390.goto("http://localhost:5000/login")
        await page_390.fill('input[name="username"]', "testuser_screenshot4")
        await page_390.fill('input[name="pin"]', "1234")
        await page_390.click('button[type="submit"]')
        await page_390.wait_for_timeout(3000)
        
        # Open drawer
        await page_390.click('.navbar-toggler, [data-bs-target="#appMenu"]')
        await page_390.wait_for_timeout(1000) # Wait for animation
        await page_390.screenshot(path="C:/Users/Yajat Sharma/.gemini/antigravity/brain/392e3157-7015-441e-abc7-d5c6f835017f/drawer_390px.png")
        print("Mobile 390px screenshot saved.")
        await mobile_390_context.close()
        
        # 3. Mobile Test (375x812 - iPhone X/11 Pro)
        mobile_375_context = await browser.new_context(viewport={"width": 375, "height": 812})
        page_375 = await mobile_375_context.new_page()
        await page_375.goto("http://localhost:5000/login")
        await page_375.fill('input[name="username"]', "testuser_screenshot4")
        await page_375.fill('input[name="pin"]', "1234")
        await page_375.click('button[type="submit"]')
        await page_375.wait_for_timeout(3000)
        
        # Open drawer
        await page_375.click('.navbar-toggler, [data-bs-target="#appMenu"]')
        await page_375.wait_for_timeout(1000) # Wait for animation
        await page_375.screenshot(path="C:/Users/Yajat Sharma/.gemini/antigravity/brain/392e3157-7015-441e-abc7-d5c6f835017f/drawer_375px.png")
        print("Mobile 375px screenshot saved.")
        await mobile_375_context.close()
        
        # 4. Mobile Test (430x932 - iPhone 14 Pro Max)
        mobile_430_context = await browser.new_context(viewport={"width": 430, "height": 932})
        page_430 = await mobile_430_context.new_page()
        await page_430.goto("http://localhost:5000/login")
        await page_430.fill('input[name="username"]', "testuser_screenshot4")
        await page_430.fill('input[name="pin"]', "1234")
        await page_430.click('button[type="submit"]')
        await page_430.wait_for_timeout(3000)
        
        # Open drawer
        await page_430.click('.navbar-toggler, [data-bs-target="#appMenu"]')
        await page_430.wait_for_timeout(1000) # Wait for animation
        await page_430.screenshot(path="C:/Users/Yajat Sharma/.gemini/antigravity/brain/392e3157-7015-441e-abc7-d5c6f835017f/drawer_430px.png")
        print("Mobile 430px screenshot saved.")
        await mobile_430_context.close()
        
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
