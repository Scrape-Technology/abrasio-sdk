"""Solve a Cloudflare Turnstile / interstitial challenge (local or cloud mode)."""

import asyncio
from abrasio import Abrasio, solve_cloudflare


async def main():
    async with Abrasio(headless=False) as browser:
        page = await browser.new_page()
        await page.goto("https://nopecha.com/demo/cloudflare")
        print("solved:", await solve_cloudflare(page))
        await page.screenshot(path="cloudflare_solved.png")


asyncio.run(main())
