"""
Abrasio - Undetected Web Scraping SDK

A unified SDK for stealth web scraping powered by Patchright:
- Local (Free): Browser on your machine with anti-detection
- Cloud (Paid): Browser in Abrasio cloud with real fingerprints

Features:
- Patchright integration (undetected Playwright fork)
- Human-like behavior simulation (Bezier mouse, typing, scrolling)
- TLS fingerprinting via curl_cffi (JA3/JA4 matching)
- BrowserForge fingerprint generation (optional)
- Unified API for local and cloud modes

Usage:
    # Free mode - local browser with stealth
    async with Abrasio() as browser:
        page = await browser.new_page()
        await page.goto("https://example.com")

    # Paid mode - cloud browser
    async with Abrasio(api_key="sk_live_xxx") as browser:
        page = await browser.new_page()
        await page.goto("https://example.com")

    # With human-like behavior
    from abrasio.utils import human_click, human_type

    await human_click(page, "button#submit")
    await human_type(page, "Hello world", selector="input#search")

    # HTTP requests with TLS fingerprinting (no browser needed)
    from abrasio.http import StealthClient

    async with StealthClient(region="BR") as client:
        response = await client.get("https://api.example.com/data")
        print(response.json())
"""

from ._api import Abrasio
from ._config import AbrasioConfig, FingerprintConfig
from .utils.certificates import build_client_certificate
from ._exceptions import (
    AbrasioError,
    AuthenticationError,
    SessionError,
    BrowserError,
    TimeoutError,
    InsufficientFundsError,
    RateLimitError,
    BlockedError,
)

__version__ = "0.1.6"
__all__ = [
    "Abrasio",
    "AbrasioConfig",
    "FingerprintConfig",
    "build_client_certificate",
    "AbrasioError",
    "AuthenticationError",
    "SessionError",
    "BrowserError",
    "TimeoutError",
    "InsufficientFundsError",
    "RateLimitError",
    "BlockedError",
]
