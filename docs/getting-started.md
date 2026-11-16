# Getting Started

This guide will help you get up and running with the Abrasio SDK.

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

## Installation

### 1. Install the SDK

```bash
pip install abrasio
```

### 2. Install Chrome Browser

Abrasio uses real Chrome (not Chromium) for a more realistic fingerprint:

```bash
patchright install chrome
```

### 3. Optional Dependencies

```bash
# TLS fingerprinting for HTTP requests (curl_cffi)
pip install abrasio[tls]

# Fingerprint generation utilities (BrowserForge)
pip install abrasio[fingerprint]

# Install everything
pip install abrasio[all]
```

## Your First Script

Create a file named `hello_abrasio.py`:

```python
import asyncio
from abrasio import Abrasio

async def main():
    # Create browser instance
    async with Abrasio(headless=False) as browser:
        # Create a new page
        page = await browser.new_page()

        # Navigate to a website
        await page.goto("https://example.com")

        # Get the page title
        title = await page.title()
        print(f"Page title: {title}")

        # Take a screenshot
        await page.screenshot(path="screenshot.png")

        print("Done! Check screenshot.png")

# Run the async function
asyncio.run(main())
```

Run it:

```bash
python hello_abrasio.py
```

## Understanding the Two Modes

### Local Mode (Free)

When you don't provide an API key, Abrasio runs in local mode:

- Browser runs on your machine
- Uses Patchright (stealth patches)
- Free to use
- IP is your own (use proxies for different IPs)
- FingerprintConfig available for canvas/audio noise, WebRTC blocking

```python
# Local mode - no API key
async with Abrasio() as browser:
    ...
```

### Cloud Mode (Paid)

With an API key, Abrasio connects to cloud browsers:

- Browser runs in Abrasio cloud
- Real fingerprints
- Geo-targeting support (50+ regions)
- Persistent profiles across sessions
- Live view for real-time browser streaming
- Automatic retry on rate limit with exponential backoff

```python
# Cloud mode - with API key
async with Abrasio(api_key="abr_live_xxx") as browser:
    ...
```

## Synchronous vs Asynchronous

### Async API (Recommended)

```python
import asyncio
from abrasio import Abrasio

async def main():
    async with Abrasio() as browser:
        page = await browser.new_page()
        await page.goto("https://example.com")

asyncio.run(main())
```

### Sync API

```python
from abrasio.sync_api import Abrasio

with Abrasio() as browser:
    page = browser.new_page()
    page.goto("https://example.com")
```

## Adding Human-Like Behavior

To avoid behavioral analysis detection:

```python
from abrasio import Abrasio
from abrasio.utils import human_click, human_type, human_wait

async def main():
    async with Abrasio(headless=False) as browser:
        page = await browser.new_page()
        await page.goto("https://example.com")

        # Wait like a human
        await human_wait(1, 2)

        # Click naturally (with Bezier curve movement)
        await human_click(page, "input#search")

        # Type naturally (variable speed, occasional mistakes)
        await human_type(page, "hello world")

asyncio.run(main())
```

## Using FingerprintConfig

Control browser fingerprint protections in local mode:

```python
from abrasio import Abrasio, FingerprintConfig

async with Abrasio(
    headless=False,
    fingerprint=FingerprintConfig(
        webgl=True,          # Keep WebGL enabled (default)
        webrtc=False,        # Block WebRTC IP leak (recommended with proxy)
        canvas_noise=True,   # Add noise to canvas fingerprint
        audio_noise=True,    # Add noise to audio fingerprint
    ),
) as browser:
    page = await browser.new_page()
    await page.goto("https://example.com")
```

> **Note**: FingerprintConfig is ignored in cloud mode. The cloud browser uses real collected fingerprints.

## Using Proxies

### Local Mode with Proxy

```python
async with Abrasio(proxy="http://user:pass@proxy.example.com:8080") as browser:
    page = await browser.new_page()
    await page.goto("https://httpbin.org/ip")
    print(await page.content())
```

### SOCKS5 Proxy

```python
async with Abrasio(proxy="socks5://user:pass@proxy.example.com:1080") as browser:
    ...
```

## Persistent Profiles

Keep cookies and browsing history across sessions:

```python
from abrasio import AbrasioConfig

config = AbrasioConfig(
    user_data_dir="./profiles/my_account",
)

async with Abrasio(config) as browser:
    page = await browser.new_page()
    # Cookies from previous sessions will be available
    await page.goto("https://example.com")
```

## Region Auto-Configuration

Set a region to auto-configure locale and timezone:

```python
from abrasio import AbrasioConfig

config = AbrasioConfig(region="BR")
# locale="pt-BR", timezone="America/Sao_Paulo"

config = AbrasioConfig(region="JP")
# locale="ja-JP", timezone="Asia/Tokyo"
```

Without explicit region, locale/timezone are auto-detected from your public IP.

## Testing Your Setup

Run this script to check your browser fingerprint:

```python
import asyncio
from abrasio import Abrasio

async def test_detection():
    async with Abrasio(headless=False) as browser:
        page = await browser.new_page()

        print("Testing bot.sannysoft.com...")
        await page.goto("https://bot.sannysoft.com/")
        await page.wait_for_timeout(3000)
        await page.screenshot(path="sannysoft.png")

        print("Testing CreepJS...")
        await page.goto("https://abrahamjuliot.github.io/creepjs/")
        await page.wait_for_timeout(5000)
        await page.screenshot(path="creepjs.png")

        print("\nCheck the screenshots!")
        print("- Green results = passing")
        print("- Red results = detected")

        input("Press Enter to close...")

asyncio.run(test_detection())
```

## Error Handling

```python
from abrasio import (
    Abrasio,
    AbrasioError,
    AuthenticationError,
    InsufficientFundsError,
    RateLimitError,
    SessionError,
    BlockedError,
)

try:
    async with Abrasio(api_key="abr_live_xxx") as browser:
        page = await browser.new_page()
        await page.goto("https://example.com")
except AuthenticationError:
    print("Invalid API key")
except InsufficientFundsError as e:
    print(f"Add funds. Balance: ${e.balance:.2f}")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except SessionError as e:
    print(f"Session error: {e.message}")
except AbrasioError as e:
    print(f"Error: {e.message}")
```

> The SDK automatically retries on 429 (rate limit), 502, 503, 504 with exponential backoff up to 3 times.

## Next Steps

- [Configuration Guide](configuration.md) - All configuration options
- [Fingerprint Config](fingerprint.md) - FingerprintConfig and fingerprinting
- [Human Behavior Guide](human-behavior.md) - Realistic behavior simulation
- [Cloud Mode Guide](cloud-mode.md) - Using cloud browsers
- [API Reference](api-reference.md) - Complete API documentation
