import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("http://localhost:5000/login")
        await page.fill('input[name="username"]', "testuser_screenshot")
        await page.fill('input[name="pin"]', "1234")
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(3000)
        content = await page.content()
        with open("scratch/debug.html", "w", encoding="utf-8") as f:
            f.write(content)
        await browser.close()
        print("Debug output saved to scratch/debug.html")

if __name__ == "__main__":
    asyncio.run(main())
