# Cloud Mode Guide

Complete guide to using Abrasio's cloud browser infrastructure.

## Overview

Cloud mode connects you to browsers running in Abrasio's infrastructure:

| Feature | Local Mode | Cloud Mode |
|---------|-----------|------------|
| Browser location | Your machine | Abrasio cloud |
| IP address | Your IP (or proxy) | Geo-targeted |
| Fingerprint | Real browser + FingerprintConfig | Collected from real devices |
| Cost | Free | Pay-per-use |
| Setup | Needs Chrome installed | Just API key |
| Live View | N/A | Real-time browser streaming |
| Session Recording | N/A | Playwright trace recording |
| Persistent Profiles | Local directory | Cloud-managed |

## Getting Started

### 1. Get an API Key

Contact the Abrasio team to get your API key.

### 2. Set Environment Variable

```bash
export ABRASIO_API_KEY="abr_live_xxx"
```

### 3. Use Cloud Mode

```python
import asyncio
from abrasio import Abrasio

async def main():
    async with Abrasio(api_key="abr_live_xxx", region="BR") as browser:
        page = await browser.new_page()
        await page.goto("https://example.com")
        print(await page.title())

asyncio.run(main())
```

## Configuration

### Basic Configuration

```python
from abrasio import Abrasio, AbrasioConfig

config = AbrasioConfig(
    api_key="abr_live_xxx",
    region="BR",                  # Target region
    url="https://example.com.br", # Target URL
    profile_id="my-profile",     # Persistent profile
)

async with Abrasio(config) as browser:
    ...
```

### Environment Variable

```bash
export ABRASIO_API_KEY="abr_live_xxx"
```

```python
# API key automatically loaded from environment
async with Abrasio() as browser:
    # If ABRASIO_API_KEY is set, this is cloud mode
    ...
```

## Live View

Cloud mode supports real-time browser streaming via noVNC:

```python
async with Abrasio(api_key="abr_live_xxx", region="BR") as browser:
    # Check live view URL
    if browser.live_view_url:
        print(f"Watch live: {browser.live_view_url}")

    page = await browser.new_page()
    await page.goto("https://example.com")
```

## Geo-Targeting

Target specific regions for location-aware scraping:

```python
# Target Brazil
async with Abrasio(api_key="abr_live_xxx", region="BR") as browser:
    page = await browser.new_page()
    await page.goto("https://example.com.br")

# Target United States
async with Abrasio(api_key="abr_live_xxx", region="US") as browser:
    page = await browser.new_page()
    await page.goto("https://example.com")
```

### Available Regions

| Code | Region |
|------|--------|
| `US` | United States |
| `BR` | Brazil |
| `GB` | United Kingdom |
| `DE` | Germany |
| `FR` | France |
| `ES` | Spain |
| `IT` | Italy |
| `JP` | Japan |
| `KR` | South Korea |
| `AU` | Australia |

50+ regions supported. Region auto-configures locale and timezone for the cloud browser.

## Persistent Profiles

Cloud profiles maintain state between sessions:

```python
# First session - login
async with Abrasio(api_key="abr_live_xxx", profile_id="my-account") as browser:
    page = await browser.new_page()
    await page.goto("https://example.com/login")
    # ... perform login ...

# Later session - still logged in!
async with Abrasio(api_key="abr_live_xxx", profile_id="my-account") as browser:
    page = await browser.new_page()
    await page.goto("https://example.com/dashboard")
    # Cookies preserved from previous session
```

### Profile Benefits

- Browsing history preserved
- Warmed fingerprint (realistic browsing history)

## Session Lifecycle

Understanding the cloud session lifecycle:

```
Create Session -> Wait for Ready -> Connect via CDP -> Use Browser -> Close
     |                |                 |              |           |
   PENDING         CLAIMED           READY         RUNNING    FINISHED
```

The SDK handles this automatically:

```python
async with Abrasio(api_key="abr_live_xxx") as browser:
    # Session created and connected automatically
    page = await browser.new_page()
    ...
    # Session closed automatically when exiting context
```

### Manual Session Management

```python
from abrasio import Abrasio

browser = Abrasio(api_key="abr_live_xxx")
await browser.start()  # Create and connect to session

page = await browser.new_page()
await page.goto("https://example.com")

await browser.close()  # Close session and cleanup
```

## Automatic Retry

The SDK automatically retries on transient errors with exponential backoff:

| Status Code | Description | Retry Behavior |
|-------------|-------------|----------------|
| 429 | Rate Limit | Respects `Retry-After` header |
| 502 | Bad Gateway | Exponential backoff |
| 503 | Service Unavailable | Exponential backoff |
| 504 | Gateway Timeout | Exponential backoff |

Up to 3 retries with backoff: 1s, 2s, 4s (capped at 30s if `Retry-After` header is present).

## Billing

Cloud mode is pay-per-use based on data consumption:

| Metric | Description |
|--------|-------------|
| Data consumed | Bytes downloaded through browser |
| Rate | $5 per GB |
| Minimum | ~$0.50 minimum balance required |

## Error Handling

```python
from abrasio import (
    Abrasio,
    AbrasioError,
    AuthenticationError,
    InsufficientFundsError,
    RateLimitError,
    SessionError,
    BrowserError,
    TimeoutError,
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
except BlockedError as e:
    print(f"Blocked by target: {e.url}")
except AbrasioError as e:
    print(f"Abrasio error: {e.message}")
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `AuthenticationError` | Invalid API key (401) | Check your API key |
| `InsufficientFundsError` | Balance too low (402) | Add funds |
| `RateLimitError` | Too many sessions (429) | Auto-retried by SDK |
| `SessionError` | Session failed | Retry or contact support |
| `TimeoutError` | Session didn't start | Retry |
| `BlockedError` | Target site blocked | Try different region or profile |

## Best Practices

### 1. Match Region to Target

```python
# Scraping Brazilian site? Use BR region
async with Abrasio(api_key="abr_live_xxx", region="BR", url="https://example.com.br") as browser:
    page = await browser.new_page()
    await page.goto("https://example.com.br")
```

### 2. Handle Errors Gracefully

```python
import asyncio
from abrasio import Abrasio, AbrasioError

async def scrape_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            async with Abrasio(api_key="abr_live_xxx") as browser:
                page = await browser.new_page()
                await page.goto(url)
                return await page.content()
        except AbrasioError as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

### 3. Close Sessions Properly

```python
# Use context manager (recommended)
async with Abrasio(api_key="abr_live_xxx") as browser:
    ...
# Session automatically closed

# Or manual close
browser = Abrasio(api_key="abr_live_xxx")
try:
    await browser.start()
    ...
finally:
    await browser.close()  # Always close!
```

## Comparison: Local vs Cloud

### When to Use Local Mode

- Development and testing
- Low-volume scraping
- Sites that don't check IP/fingerprint
- When you have good proxies
- Cost-sensitive projects

### When to Use Cloud Mode

- Production scraping
- High-value targets with strong anti-bot
- Need geo-targeting
- Need persistent sessions
- Need real device fingerprints
- Don't want to manage proxies
- Don't want to deal with captchas yourself

## Combining Local and Cloud

Use local mode for development, cloud for production:

```python
import os
from abrasio import Abrasio

# Development: local mode
# Production: cloud mode (set ABRASIO_API_KEY)

async def scrape(url):
    api_key = os.getenv("ABRASIO_API_KEY")  # None in dev

    async with Abrasio(api_key=api_key, headless=False) as browser:
        page = await browser.new_page()
        await page.goto(url)
        return await page.content()
```

```bash
# Development
python scraper.py

# Production
ABRASIO_API_KEY="abr_live_xxx" python scraper.py
```
