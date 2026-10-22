# Abrasio SDK Documentation

Welcome to the Abrasio SDK documentation.

## Quick Links

| Guide | Description |
|-------|-------------|
| [Getting Started](getting-started.md) | Installation and first steps |
| [Configuration](configuration.md) | All configuration options |
| [Fingerprint Config](fingerprint.md) | FingerprintConfig and browser fingerprinting |
| [Cloudflare](cloudflare.md) | Cloudflare Turnstile auto-solve |
| [Human Behavior](human-behavior.md) | Mouse, typing, scrolling simulation |
| [Cloud Mode](cloud-mode.md) | Using cloud browser infrastructure |
| [API Reference](api-reference.md) | Complete API documentation |

## Overview

Abrasio SDK is an undetected web scraping library powered by [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) with:

- **Anti-Detection**: Bypasses Runtime.enable, CDP detection, and navigator.webdriver
- **Cloudflare Turnstile**: `solve_cloudflare=True` solves challenges automatically (local and cloud)
- **Human Behavior**: Bezier curve mouse movements, natural typing, smooth scrolling
- **FingerprintConfig**: Control WebGL, WebRTC, canvas/audio noise per session (local mode)
- **TLS Fingerprinting**: curl_cffi for JA3/JA4 matching on HTTP requests
- **Two Modes**: Free local mode or paid cloud mode with real fingerprints
- **Automatic Retry**: Exponential backoff on 429, 502, 503, 504
- **Playwright API**: Drop-in replacement, same API you know

## Installation

```bash
# Install SDK
pip install abrasio

# Install Chrome browser
patchright install chrome

# Optional: TLS fingerprinting for HTTP requests
pip install abrasio[tls]

# Optional: fingerprint generation utilities
pip install abrasio[fingerprint]

# Install everything
pip install abrasio[all]
```

## Quick Start

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

## Features at a Glance

### Anti-Detection (Automatic)

Patchright handles anti-detection automatically:

- No `Runtime.enable` leak
- No CDP detection via protocol-level patches
- No `navigator.webdriver` flag (`--disable-blink-features=AutomationControlled`)
- No `--enable-automation` argument
- Real Chrome browser fingerprint

### FingerprintConfig (Local Mode)

```python
from abrasio import Abrasio, FingerprintConfig

async with Abrasio(
    headless=False,
    fingerprint=FingerprintConfig(
        canvas_noise=True,   # Randomize canvas fingerprint
        audio_noise=True,    # Randomize audio fingerprint
        webrtc=False,        # Block WebRTC IP leak
    ),
) as browser:
    page = await browser.new_page()
```

### Human Behavior (Optional)

```python
from abrasio.utils import human_click, human_type

await human_click(page, "button#submit")
await human_type(page, "search query", selector="input")
```

### TLS Fingerprinting (HTTP)

```python
from abrasio.http import StealthClient

async with StealthClient(region="BR") as client:
    response = await client.get("https://example.com")
```

### Cloud Mode (Optional)

```python
async with Abrasio(api_key="sk_live_xxx", region="BR") as browser:
    page = await browser.new_page()
    # Browser with real fingerprint and geo-targeting
```

## Architecture

```
+-----------------------------------------------------+
|                    Abrasio SDK                       |
+-----------------------------------------------------+
|  +--------------+              +-----------------+   |
|  | Local Mode   |              |   Cloud Mode    |   |
|  |   (Free)     |              |    (Paid)       |   |
|  |              |              |                 |   |
|  | Patchright   |              |  Abrasio API    |   |
|  |  + Real      |              |  + Real         |   |
|  |  Chrome      |              |    Fingerprints |   |
|  |  + Fingerprint|             |  + Geo-Target   |   |
|  |    Config    |              |  + Live View    |   |
|  +--------------+              +-----------------+   |
+-----------------------------------------------------+
|              Human Behavior Utilities                |
|   (Bezier mouse, natural typing, smooth scroll)      |
+-----------------------------------------------------+
|           TLS Fingerprinting (StealthClient)         |
|   (curl_cffi, JA3/JA4 matching, browser TLS)        |
+-----------------------------------------------------+
```

## Project Structure

```
abrasio-sdk/
+-- abrasio/
|   +-- __init__.py          # Public API exports
|   +-- _api.py              # Abrasio class (local + cloud)
|   +-- _config.py           # AbrasioConfig, FingerprintConfig
|   +-- _exceptions.py       # Exception hierarchy
|   +-- local/
|   |   +-- browser.py       # StealthBrowser (Patchright)
|   +-- cloud/
|   |   +-- browser.py       # CloudBrowser (API + CDP)
|   |   +-- api_client.py    # HTTP client with retry
|   +-- http/
|   |   +-- client.py        # StealthClient (curl_cffi TLS)
|   +-- sync_api/
|   |   +-- _sync.py         # Synchronous wrapper
|   +-- utils/
|       +-- human.py         # Human behavior simulation
|       +-- fingerprint.py   # Region config, validation
|       +-- geolocation.py   # IP-based locale detection
+-- examples/
|   +-- basic_local.py       # Local mode example
|   +-- basic_cloud.py       # Cloud mode example
+-- docs/                    # Documentation
+-- pyproject.toml
+-- README.md
```

## License

Proprietary - Scrape Technology
