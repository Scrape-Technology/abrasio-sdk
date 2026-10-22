# Configuration Guide

Complete guide to configuring the Abrasio SDK.

## AbrasioConfig

The `AbrasioConfig` class holds all configuration options.

```python
from abrasio import AbrasioConfig

config = AbrasioConfig(
    # ... options
)
```

## Configuration Options

### Core Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `api_key` | `str | None` | `ABRASIO_API_KEY` env | API key for cloud mode. `None` = local mode |
| `api_url` | `str` | `ABRASIO_API_URL` env or `http://localhost:8000` | API base URL |
| `url` | `str | None` | `None` | Target URL (used in cloud mode for session creation) |

```python
# Local mode
config = AbrasioConfig(api_key=None)

# Cloud mode
config = AbrasioConfig(api_key="sk_live_xxx")

# Custom API URL
config = AbrasioConfig(
    api_key="sk_live_xxx",
    api_url="https://api.abrasio.io",
)
```

### Browser Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `headless` | `bool` | `True` | Run browser without visible window |
| `proxy` | `str | None` | `None` | Proxy URL |
| `timeout` | `int` | `30000` | Default timeout in milliseconds |

```python
# Visible browser (recommended for stealth)
config = AbrasioConfig(headless=False)

# With proxy
config = AbrasioConfig(
    proxy="http://user:pass@proxy.example.com:8080",
)

# SOCKS5 proxy
config = AbrasioConfig(
    proxy="socks5://user:pass@proxy.example.com:1080",
)

# Custom timeout
config = AbrasioConfig(timeout=60000)  # 60 seconds
```

### Region Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `region` | `str | None` | `None` | Target region (auto-configures locale/timezone) |
| `locale` | `str | None` | Auto-detected | Browser locale |
| `timezone` | `str | None` | Auto-detected | Timezone ID |
| `auto_configure_region` | `bool` | `True` | Auto-configure locale/timezone from region or IP |

```python
# Auto-configure from region
config = AbrasioConfig(region="BR")
# locale="pt-BR", timezone="America/Sao_Paulo"

config = AbrasioConfig(region="JP")
# locale="ja-JP", timezone="Asia/Tokyo"
```

50+ regions supported. Mismatched settings generate warnings:

```python
config = AbrasioConfig(region="BR", timezone="America/New_York")
print(config.region_warnings)
# ['Timezone mismatch: using America/New_York but region BR expects America/Sao_Paulo']
```

Without explicit region, locale/timezone are auto-detected from your public IP.

### FingerprintConfig (Local Mode Only)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `fingerprint` | `FingerprintConfig` | `FingerprintConfig()` | Fingerprint protection settings |

```python
from abrasio import AbrasioConfig, FingerprintConfig

config = AbrasioConfig(
    fingerprint=FingerprintConfig(
        webgl=True,          # Keep WebGL enabled (default)
        webrtc=False,        # Block WebRTC IP leak
        canvas_noise=True,   # Add noise to canvas fingerprint
        audio_noise=True,    # Add noise to audio fingerprint
    ),
)
```

| FingerprintConfig Option | Default | Description |
|--------------------------|---------|-------------|
| `webgl` | `True` | Enable WebGL APIs. Disabling is a strong bot signal. |
| `webrtc` | `True` | Enable WebRTC. Set `False` with proxy to prevent real IP leak. |
| `canvas_noise` | `False` | Add imperceptible noise to canvas reads. Randomizes fingerprint. |
| `audio_noise` | `False` | Add noise to AudioContext reads. Randomizes fingerprint. |

> **Cloud mode**: FingerprintConfig is completely ignored. The cloud browser uses real collected fingerprints

### Profile Persistence

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `user_data_dir` | `str | None` | `None` | Directory for persistent profile (local mode) |

```python
# Persistent profile
config = AbrasioConfig(
    user_data_dir="./profiles/my_account",
)
```

Benefits of persistent profiles:
- Cookies saved between sessions
- Local storage preserved
- Browsing history maintained
- Login sessions persist

### Cloud Mode Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `region` | `str | None` | `None` | Target region for geo-targeting |
| `profile_id` | `str | None` | `None` | Cloud profile ID for persistent sessions |
| `url` | `str | None` | `None` | Target URL for cloud session |

```python
# Target Brazil with persistent cloud profile
config = AbrasioConfig(
    api_key="sk_live_xxx",
    region="BR",
    url="https://example.com.br",
    profile_id="my-brazil-profile",
)
```

### Advanced Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `stealth` | `bool` | `True` | Enable stealth mode |
| `extra_args` | `list[str]` | `[]` | Additional Chrome launch arguments |
| `debug` | `bool` | `False` | Enable debug logging |
| `solve_cloudflare` | `bool` | `False` | Auto-solve Cloudflare Turnstile after every `page.goto()`. See [Cloudflare](cloudflare.md) |

```python
# With extra Chrome arguments
config = AbrasioConfig(
    extra_args=[
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ],
)

# Debug mode
config = AbrasioConfig(debug=True)
```

### Local launch details

In local mode the SDK sets these automatically to look like a regular desktop Chrome:

- **Language by flag:** `locale` is passed as `--lang` / `--accept-lang`, so workers, `Intl` and
  `Accept-Language` all agree (the context `locale` option only patches the main thread).
- **Headless User-Agent:** `HeadlessChrome` is replaced by `Chrome/<major>`, where `<major>` is
  the version of the installed Chrome (Windows registry or `google-chrome --version`), falling
  back to the Chromium version bundled with Patchright.
- **Desktop signals:** `color_scheme="dark"` (passes creepjs' `prefersLightColor` check),
  `--start-maximized`, `--window-position=0,0` and `--blink-settings` (hover + fine pointer).
- **Canvas noise** stays off by default: Google reCAPTCHA detects it.

### Deprecated Options

| Option | Status | Note |
|--------|--------|------|
| `user_agent` | Deprecated | Don't set - creates fingerprint mismatch |
| `viewport` | Deprecated | Don't set - uses `no_viewport` for realistic behavior |

## Environment Variables

Configuration can also be set via environment variables:

| Variable | Config Option | Description |
|----------|--------------|-------------|
| `ABRASIO_API_KEY` | `api_key` | API key for cloud mode |
| `ABRASIO_API_URL` | `api_url` | API base URL |

```bash
# Set environment variables
export ABRASIO_API_KEY="sk_live_xxx"
export ABRASIO_API_URL="https://api.abrasio.io"
```

```python
# Config will use environment variables automatically
config = AbrasioConfig()  # api_key read from ABRASIO_API_KEY
```

## Configuration Patterns

### Simple Local Mode

```python
from abrasio import Abrasio

async with Abrasio(headless=False) as browser:
    ...
```

### With Config Object

```python
from abrasio import Abrasio, AbrasioConfig, FingerprintConfig

config = AbrasioConfig(
    headless=False,
    region="BR",
    user_data_dir="./profiles/default",
    fingerprint=FingerprintConfig(
        canvas_noise=True,
        webrtc=False,
    ),
)

async with Abrasio(config) as browser:
    ...
```

### API Key as First Argument

```python
# Shorthand for cloud mode
async with Abrasio("sk_live_xxx") as browser:
    ...

# Equivalent to:
async with Abrasio(api_key="sk_live_xxx") as browser:
    ...
```

## Configuration for Different Use Cases

### High Stealth Local Scraping

```python
config = AbrasioConfig(
    headless=False,                       # Visible browser
    user_data_dir="./profiles/stealth",
    fingerprint=FingerprintConfig(
        canvas_noise=True,                # Randomize canvas
        audio_noise=True,                 # Randomize audio
        webrtc=False,                     # Block WebRTC IP leak
    ),
    # Don't set user_agent or viewport!
)
```

### Cloud Scraping with Geo-Targeting

```python
config = AbrasioConfig(
    api_key="sk_live_xxx",
    region="BR",
    url="https://example.com.br",
    profile_id="brazil-scraper",
)
```

### Docker/Server Environment

```python
config = AbrasioConfig(
    headless=True,
    extra_args=[
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ],
)
```

### Rotating Proxies

```python
import random

proxies = [
    "http://proxy1.example.com:8080",
    "http://proxy2.example.com:8080",
    "http://proxy3.example.com:8080",
]

config = AbrasioConfig(
    proxy=random.choice(proxies),
    fingerprint=FingerprintConfig(webrtc=False),  # Block IP leak
)
```

## Converting Config to Dictionary

```python
config = AbrasioConfig(
    headless=False,
    region="BR",
)

# Get as dictionary
config_dict = config.to_dict()
print(config_dict)
# {'api_key': None, 'headless': False, 'locale': 'pt-BR', 'fingerprint': {...}, ...}
```

## Checking Mode

```python
config = AbrasioConfig(api_key="sk_live_xxx")

print(config.is_cloud_mode)  # True
print(config.is_local_mode)  # False
```
