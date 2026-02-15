"""
Basic example using Abrasio in local (free) mode with Patchright.

This example demonstrates how to use Abrasio with maximum anti-detection:
- Uses Patchright (undetected Playwright fork)
- Uses real Chrome (channel="chrome")
- Uses persistent context for better fingerprint
- No custom user_agent (creates fingerprint mismatch)
- No viewport override (no_viewport for realistic behavior)

Before running:
    pip install abrasio
    patchright install chrome  # Install real Chrome, not Chromium
"""

import asyncio
from abrasio import Abrasio


async def main():
    # Local mode - no API key needed
    # headless=False recommended for maximum stealth

    async with Abrasio(headless=False) as browser:
        page = await browser.new_page()

        # Test against bot detection sites
        print("Testing against bot detection...")

        # Test 1: Sannysoft
        await page.goto("https://bot.sannysoft.com/")
        await page.wait_for_timeout(3000)
        await page.screenshot(path="test_sannysoft.png", full_page=True)
        print("Sannysoft test saved to test_sannysoft.png")

        # Test 2: Fingerprint.com (BotD)
        await page.goto("https://demo.fingerprint.com/playground")
        await page.wait_for_timeout(3000)
        await page.screenshot(path="test_fingerprint.png", full_page=True)
        print("Fingerprint.com test saved to test_fingerprint.png")

        # Test 3: CreepJS
        await page.goto("https://abrahamjuliot.github.io/creepjs/")
        await page.wait_for_timeout(5000)
        await page.screenshot(path="test_creepjs.png", full_page=True)
        print("CreepJS test saved to test_creepjs.png")

        print("\nCheck the screenshots to verify anti-detection is working!")
        print("Green = pass, Red = fail")

        # Keep browser open for manual inspection
        input("\nPress Enter to close browser...")


if __name__ == "__main__":
    asyncio.run(main())
