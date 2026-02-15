"""
Basic example using Abrasio in cloud (paid) mode.

This example demonstrates how to use Abrasio with the cloud browser
service using an API key.

Before running:
    pip install abrasio
    export ABRASIO_API_KEY=sk_live_xxx
"""

import asyncio
import os
from abrasio import Abrasio
from abrasio.utils import human_scroll, human_wait, simulate_reading


async def main():
    # Get API key from environment
    api_key = os.getenv("ABRASIO_API_KEY")
    if not api_key:
        print("Set ABRASIO_API_KEY environment variable to use cloud mode")
        print("Example: export ABRASIO_API_KEY=sk_live_xxx")
        return

    # Cloud mode - with API key and region
    # For local testing use: api_url="http://localhost:8000"
    async with Abrasio(
        api_key=api_key,
        # api_url="http://localhost:8000",  # Uncomment for local testing
        region="BR",
        url="https://google.com.br",
    ) as browser:
        page = await browser.new_page()

        # Live view URL (if enabled on server)
        if browser.live_view_url:
            print(f"Watch live: {browser.live_view_url}")

        # Navigate to a page
        await page.goto("https://browserscan.net")

        # Get page title
        title = await page.title()
        print(f"Page title: {title}")

        # Wait like a human
        await human_wait(1, 3)

        # Scroll and read
        await human_scroll(page, "down", amount=400, smooth=True)
        await simulate_reading(page, min_seconds=2, max_seconds=5)

        # Take a screenshot
        await page.screenshot(path="cloud_screenshot.png", full_page=True)
        print("Screenshot saved to cloud_screenshot.png")


if __name__ == "__main__":
    asyncio.run(main())
