# Abrasio SDK

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Version 0.1.0](https://img.shields.io/badge/version-0.1.0-blue.svg)]()

**Undetected web scraping SDK** inspired on [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) with human-like behavior simulation and optional cloud browser support.

## Features

| Feature | Description |
|---------|-------------|
| **Undetected** | Patchright bypasses Runtime.enable and CDP detection |
| **Free Local Mode** | Run on your machine with anti-detection patches |
| **Cloud Mode** | Real fingerprints(paid) |
| **Human Behavior** | Bezier mouse movements, natural typing, smooth scrolling |
| **TLS Fingerprinting** | curl_cffi for JA3/JA4 TLS fingerprint matching |
| **Fingerprint Config** | Control WebGL, WebRTC, canvas/audio noise per session |
| **Playwright API** | Same API you already know |

## Anti-Detection Status

| Technique | Status | Notes |
|-----------|--------|-------|
| Patchright (CDP leak) | Implemented | Protocol-level, not JS patches |
| navigator.webdriver | Implemented | `--disable-blink-features=AutomationControlled` |
| Human behavior (Bezier) | Implemented | Mouse, typing, scrolling |
| TLS fingerprinting (JA3/JA4) | Implemented | via curl_cffi for HTTP requests |
| Canvas noise | Implemented | Optional via `FingerprintConfig(canvas_noise=True)` |
| Audio noise | Implemented | Optional via `FingerprintConfig(audio_noise=True)` |
| WebRTC IP leak protection | Implemented | Via `FingerprintConfig(webrtc=False)` |
| WebGL control | Implemented | Enabled by default, disable via config |
| Timezone/Locale consistency | Auto-validated | Auto-configures from region or IP |
| Retry on rate limit | Implemented | Exponential backoff with Retry-After |

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [FingerprintConfig](#fingerprintconfig)
- [Human-Like Behavior](#human-like-behavior)
- [TLS Fingerprinting (HTTP)](#tls-fingerprinting-http)
- [Configuration](#configuration)
- [Cloud Mode](#cloud-mode-paid)
- [Error Handling](#error-handling)
- [API Reference](#api-reference)
- [Best Practices](#best-practices)

## Installation

```bash
# Install SDK
pip install abrasio

# Install real Chrome (NOT Chromium) for maximum stealth
patchright install chrome

# Optional: TLS fingerprinting for HTTP requests
pip install abrasio[tls]

# Optional: fingerprint generation utilities
pip install abrasio[fingerprint]

# Install everything
pip install abrasio[all]
```

### Requirements

- Python 3.8+
- Chrome browser (installed via `patchright install chrome`)

## Quick Start

### Local Mode (Free)

```python
import asyncio
from abrasio import Abrasio

async def main():
    async with Abrasio(headless=False) as browser:
        page = await browser.new_page()
        await page.goto("https://example.com")
        print(await page.title())

asyncio.run(main())
```

### Cloud Mode (Paid)

```python
import asyncio
from abrasio import Abrasio

async def main():
    async with Abrasio(
        api_key="sk_live_xxx",
        region="BR",
        url="https://example.com.br",
    ) as browser:
        page = await browser.new_page()
        await page.goto("https://example.com.br")
        print(await page.title())

asyncio.run(main())
```

### Synchronous API

```python
from abrasio.sync_api import Abrasio

with Abrasio(headless=False) as browser:
    page = browser.new_page()
    page.goto("https://example.com")
    print(page.title())
```

## FingerprintConfig

Control browser fingerprint protections in **local mode only**. In cloud mode, the cloud browser handles all fingerprinting automatically.

```python
from abrasio import Abrasio, FingerprintConfig

async with Abrasio(
    headless=False,
    fingerprint=FingerprintConfig(
        webgl=True,          # Keep WebGL enabled (default). False blocks it.
        webrtc=False,        # Block WebRTC IP leak (recommended with proxy)
        canvas_noise=True,   # Add noise to canvas fingerprint
        audio_noise=True,    # Add noise to audio fingerprint
    ),
) as browser:
    page = await browser.new_page()
    await page.goto("https://example.com")
```

| Option | Default | Description |
|--------|---------|-------------|
| `webgl` | `True` | Enable WebGL APIs. Disabling is a strong bot signal. |
| `webrtc` | `True` | Enable WebRTC. Set `False` with proxy to prevent real IP leak. |
| `canvas_noise` | `False` | Add imperceptible noise to canvas reads. Randomizes fingerprint. |
| `audio_noise` | `False` | Add noise to AudioContext reads. Randomizes fingerprint. |

> **Cloud mode**: `FingerprintConfig` is completely ignored. The cloud browser uses real collected fingerprints 

## Human-Like Behavior

Utilities for simulating realistic human behavior to bypass behavioral analysis.

### Mouse Movement (Bezier Curves)

```python
from abrasio.utils import human_move_to, human_click

# Move mouse with natural Bezier curve trajectory
await human_move_to(page, x=500, y=300)

# Click with natural movement and random offset
await human_click(page, "button#submit")
```

### Natural Typing

```python
from abrasio.utils import human_type

await human_type(
    page,
    "Hello, World!",
    selector="input#search",
    mistake_probability=0.02,
    think_pause_probability=0.05,
)
```

### Smooth Scrolling

```python
from abrasio.utils import human_scroll, simulate_reading

await human_scroll(page, "down", amount=400, smooth=True)
await simulate_reading(page, min_seconds=3, max_seconds=8)
```

### All Utilities

```python
from abrasio.utils import (
    human_move_to,      # Bezier curve mouse movement
    human_click,        # Natural click with movement
    human_type,         # Variable-speed typing with mistakes
    human_scroll,       # Smooth scrolling with momentum
    human_wait,         # Random wait (skewed distribution)
    random_delay,       # Simple random delay
    simulate_reading,   # Simulate page reading behavior
)
```

## TLS Fingerprinting (HTTP)

For HTTP requests **outside the browser**, use `StealthClient` which matches real browser TLS fingerprints via [curl_cffi](https://github.com/yifeikong/curl_cffi).

```bash
pip install abrasio[tls]
```

```python
from abrasio.http import StealthClient

# Async
async with StealthClient() as client:
    response = await client.get("https://example.com")
    print(response.text)

# With region (auto-sets Accept-Language)
async with StealthClient(region="BR") as client:
    response = await client.get("https://example.com.br")

# With proxy
async with StealthClient(proxy="http://user:pass@host:8080") as client:
    response = await client.get("https://example.com")

# Rotate browser version on each request
async with StealthClient(rotate_impersonation=True) as client:
    for url in urls:
        response = await client.get(url)
```

## Configuration

### AbrasioConfig

```python
from abrasio import Abrasio, AbrasioConfig, FingerprintConfig

config = AbrasioConfig(
    # Mode: None = local (free), "sk_xxx" = cloud (paid)
    api_key=None,

    # Browser
    headless=False,                  # Visible = more stealthy
    proxy="http://user:pass@host:8080",
    timeout=30000,

    # Region (auto-configures locale/timezone)
    region="BR",

    # Fingerprint (local mode only)
    fingerprint=FingerprintConfig(
        webgl=True,
        webrtc=False,
        canvas_noise=True,
        audio_noise=True,
    ),

    # Profile persistence
    user_data_dir="./my_profile",

    # Cloud mode
    profile_id="my-profile",

    # Advanced
    extra_args=[],
    debug=False,
)

async with Abrasio(config) as browser:
    ...
```

### Region Auto-Configuration

```python
config = AbrasioConfig(region="BR")
# locale="pt-BR", timezone="America/Sao_Paulo"

config = AbrasioConfig(region="JP")
# locale="ja-JP", timezone="Asia/Tokyo"
```

50+ regions supported. If you set a mismatched timezone, you'll get a warning:

```python
config = AbrasioConfig(region="BR", timezone="America/New_York")
print(config.region_warnings)
# ['Timezone mismatch: using America/New_York but region BR expects America/Sao_Paulo']
```

Without explicit region, locale/timezone are auto-detected from your public IP.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ABRASIO_API_KEY` | API key for cloud mode | `None` |
| `ABRASIO_API_URL` | API base URL | `http://localhost:8000` |

## Cloud Mode (Paid)

With an API key, you get access to the Abrasio cloud infrastructure:

| Feature | Description |
|---------|-------------|
| **Real Fingerprints** | collected device data |
| **Geo-Targeting** | Target specific countries/regions |
| **Persistent Profiles** | Maintain cookies and history across sessions |
| **Session Recording** | Playwright trace recording for debugging |
| **Live View** | Real-time browser streaming via noVNC |
| **Automatic Retry** | SDK retries on rate limit (429) with backoff |

```python
from abrasio import Abrasio

async with Abrasio(
    api_key="sk_live_xxx",
    region="BR",
    url="https://target-site.com.br",
    profile_id="my-profile",
) as browser:
    page = await browser.new_page()

    # Live view URL (if enabled on server)
    if browser.live_view_url:
        print(f"Watch live: {browser.live_view_url}")

    await page.goto("https://target-site.com.br")
    print(await page.title())
```

## Error Handling

```python
from abrasio import (
    Abrasio,
    AbrasioError,           # Base error
    AuthenticationError,    # Invalid API key (401)
    InsufficientFundsError, # Not enough balance (402)
    RateLimitError,         # Too many sessions (429) - auto-retried
    SessionError,           # Session creation/management error
    BrowserError,           # Browser operation error
    TimeoutError,           # Operation timeout
    BlockedError,           # Target site blocked request
)

try:
    async with Abrasio(api_key="sk_live_xxx") as browser:
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

> **Note**: The SDK automatically retries on 429 (rate limit), 502, 503, 504 with exponential backoff up to 3 times.

## API Reference

### Abrasio

```python
class Abrasio:
    def __init__(
        self,
        config: Optional[AbrasioConfig] = None,
        *,
        api_key: Optional[str] = None,
        headless: bool = True,
        proxy: Optional[str] = None,
        stealth: bool = True,
        **kwargs,
    ): ...

    async def start(self) -> "Abrasio": ...
    async def close(self) -> None: ...
    async def new_page(self) -> Page: ...
    async def new_context(self, **kwargs) -> BrowserContext: ...

    @property
    def browser(self): ...       # Browser (cloud) or BrowserContext (local)
    @property
    def is_cloud(self) -> bool: ...
    @property
    def is_local(self) -> bool: ...
    @property
    def live_view_url(self) -> Optional[str]: ...  # Cloud mode only
```

### Human Utilities

```python
async def human_move_to(page, x, y, *, min_time=0.1, max_time=1.5): ...
async def human_click(page, selector=None, *, offset_range=5, move_first=True): ...
async def human_type(page, text, selector=None, *, mistake_probability=0.02): ...
async def human_scroll(page, direction="down", amount=None, *, smooth=True): ...
async def random_delay(min_ms=100, max_ms=500): ...
async def human_wait(min_seconds=0.5, max_seconds=2.0): ...
async def simulate_reading(page, min_seconds=2.0, max_seconds=8.0): ...
```

### StealthClient (TLS)

```python
from abrasio.http import StealthClient, BrowserImpersonation

class StealthClient:
    def __init__(self, impersonate=BrowserImpersonation.DEFAULT,
                 proxy=None, region=None, rotate_impersonation=False): ...

    async def get(self, url, **kwargs) -> StealthResponse: ...
    async def post(self, url, **kwargs) -> StealthResponse: ...
```

## Best Practices

1. **Use `headless=False`** for maximum stealth
2. **Don't set `user_agent`** — let real Chrome handle it (fingerprint mismatch)
3. **Don't set `viewport`** — uses `no_viewport` for realistic behavior
4. **Add human behavior** between actions (`human_wait`, `human_click`)
5. **Use persistent profiles** with `user_data_dir` for cookie persistence
6. **Use `region`** to auto-configure locale/timezone consistently
7. **Set `webrtc=False`** when using a proxy (prevents IP leak)
8. **Test against bot detection sites** before production deployment

## Testing Anti-Detection

```python
import asyncio
from abrasio import Abrasio

async def test():
    async with Abrasio(headless=False) as browser:
        page = await browser.new_page()

        await page.goto("https://bot.sannysoft.com/")
        await page.screenshot(path="sannysoft.png")

        await page.goto("https://abrahamjuliot.github.io/creepjs/")
        await page.wait_for_timeout(5000)
        await page.screenshot(path="creepjs.png")

asyncio.run(test())
```

## Project Structure

```
abrasio-sdk/
├── abrasio/
│   ├── __init__.py          # Public API exports
│   ├── _api.py              # Abrasio class (local + cloud)
│   ├── _config.py           # AbrasioConfig, FingerprintConfig
│   ├── _exceptions.py       # Exception hierarchy
│   ├── local/
│   │   └── browser.py       # StealthBrowser (Patchright)
│   ├── cloud/
│   │   ├── browser.py       # CloudBrowser (API + CDP)
│   │   └── api_client.py    # HTTP client with retry
│   ├── http/
│   │   └── client.py        # StealthClient (curl_cffi TLS)
│   ├── sync_api/
│   │   └── _sync.py         # Synchronous wrapper
│   └── utils/
│       ├── human.py         # Human behavior simulation
│       ├── fingerprint.py   # Region config, validation
│       └── geolocation.py   # IP-based locale detection
├── examples/
│   ├── basic_local.py       # Local mode example
│   ├── basic_cloud.py       # Cloud mode example
│   ├── human_behavior.py    # Human behavior demo
│   ├── fingerprint_check.py # Fingerprint validation
│   └── tls_fingerprint.py   # TLS fingerprinting
├── docs/                    # Documentation
└── pyproject.toml
```

## References

- [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) - Undetected Playwright fork
- [curl_cffi](https://github.com/yifeikong/curl_cffi) - TLS fingerprinting HTTP client
- [BrowserForge](https://github.com/daijro/browserforge) - Fingerprint generation
- [Ghost Cursor](https://github.com/Xetera/ghost-cursor) - Bezier curve mouse movements

## License

Proprietary - Scrape Technology
