# API Reference

Complete API reference for the Abrasio SDK.

## Core Classes

### Abrasio

Main class for browser automation.

```python
class Abrasio:
    """
    Unified interface for stealth web scraping.

    Automatically selects between local (free) and cloud (paid) modes
    based on whether an API key is provided.
    """

    def __init__(
        self,
        config: Optional[Union[AbrasioConfig, str]] = None,
        *,
        api_key: Optional[str] = None,
        headless: bool = True,
        proxy: Optional[str] = None,
        stealth: bool = True,
        **kwargs,
    ) -> None:
        """
        Initialize Abrasio.

        Args:
            config: AbrasioConfig object or API key string
            api_key: Abrasio API key (enables cloud mode)
            headless: Run browser in headless mode
            proxy: Proxy URL for local mode
            stealth: Enable stealth patches
            **kwargs: Additional config options (region, url, fingerprint, etc.)
        """

    async def start(self) -> "Abrasio":
        """Start the browser. Returns self for chaining."""

    async def close(self) -> None:
        """Close the browser and cleanup resources."""

    async def new_page(self) -> Page:
        """Create a new page with stealth enhancements."""

    async def new_context(self, **kwargs) -> BrowserContext:
        """
        Create a new browser context.

        Note: With Patchright persistent context, this returns the main context.
        Creating multiple contexts can reduce stealth.
        """

    @property
    def browser(self):
        """Get the underlying browser or context object.

        In cloud mode: returns the Patchright Browser object.
        In local mode: returns the BrowserContext (persistent context).
        """

    @property
    def is_cloud(self) -> bool:
        """Check if running in cloud mode."""

    @property
    def is_local(self) -> bool:
        """Check if running in local mode."""

    @property
    def live_view_url(self) -> Optional[str]:
        """Get the live view URL for real-time browser streaming (cloud mode only)."""

    # Context manager support
    async def __aenter__(self) -> "Abrasio": ...
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...
```

### AbrasioConfig

Configuration dataclass.

```python
@dataclass
class AbrasioConfig:
    """Configuration for Abrasio browser."""

    # Core settings
    api_key: Optional[str] = None           # From ABRASIO_API_KEY env
    api_url: str = "https://abrasio-api.scrapetechnology.com"  # From ABRASIO_API_URL env
    url: Optional[str] = None               # Target URL (cloud mode)

    # Browser settings
    headless: bool = True
    proxy: Optional[str] = None
    timeout: int = 30000

    # Stealth settings (local mode)
    stealth: bool = True
    locale: Optional[str] = None            # Auto-detected from region/IP
    timezone: Optional[str] = None          # Auto-detected from region/IP
    user_agent: Optional[str] = None        # DEPRECATED
    viewport: Optional[Dict[str, int]] = None  # DEPRECATED
    user_data_dir: Optional[str] = None

    # Cloud settings (paid mode)
    region: Optional[str] = None
    profile_id: Optional[str] = None

    # Region auto-configuration
    auto_configure_region: bool = True

    # Fingerprint protection (local mode only - ignored in cloud mode)
    fingerprint: FingerprintConfig = FingerprintConfig()

    # Advanced
    extra_args: List[str] = []
    debug: bool = False

    @property
    def is_cloud_mode(self) -> bool:
        """Check if running in cloud mode (has API key starting with 'sk_')."""

    @property
    def is_local_mode(self) -> bool:
        """Check if running in local mode (no API key)."""

    @property
    def region_warnings(self) -> List[str]:
        """Get any region consistency warnings."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
```

### FingerprintConfig

Fingerprint protection settings (local mode only).

```python
@dataclass
class FingerprintConfig:
    """
    Fingerprint protection settings (local mode only).

    In cloud mode, the cloud browse handles all
    fingerprinting. These settings are completely ignored with an API key.
    """

    webgl: bool = True          # Enable WebGL APIs
    webrtc: bool = True         # Enable WebRTC (False = block IP leak)
    canvas_noise: bool = False  # Add noise to canvas fingerprint
    audio_noise: bool = False   # Add noise to AudioContext fingerprint
```

## Exceptions

All exceptions inherit from `AbrasioError` and include a `message` attribute and optional `details` dict.

```python
class AbrasioError(Exception):
    """Base exception for all Abrasio errors."""
    message: str
    details: dict

class AuthenticationError(AbrasioError):
    """Invalid or missing API key (HTTP 401)."""

class InsufficientFundsError(AbrasioError):
    """Not enough balance for cloud mode (HTTP 402)."""
    balance: Optional[float]

class RateLimitError(AbrasioError):
    """Rate limit exceeded (HTTP 429). Auto-retried by SDK."""
    retry_after: Optional[int]

class SessionError(AbrasioError):
    """Session creation or management error."""
    session_id: Optional[str]

class BrowserError(AbrasioError):
    """Browser-related error."""

class TimeoutError(AbrasioError):
    """Operation timed out."""
    timeout_ms: Optional[int]

class BlockedError(AbrasioError):
    """Target site blocked the request."""
    url: Optional[str]
    status_code: Optional[int]
```

### Exception Hierarchy

```
AbrasioError
+-- AuthenticationError
+-- InsufficientFundsError
+-- RateLimitError
+-- SessionError
+-- BrowserError
+-- TimeoutError
+-- BlockedError
```

## Human Behavior Utilities

### human_move_to()

```python
async def human_move_to(
    page: Page,
    x: float,
    y: float,
    *,
    min_time: float = 0.1,
    max_time: float = 1.5,
) -> None:
    """
    Move mouse to position using human-like Bezier curve trajectory.

    Args:
        page: Patchright Page object
        x: Target X coordinate
        y: Target Y coordinate
        min_time: Minimum movement duration in seconds
        max_time: Maximum movement duration in seconds
    """
```

### human_click()

```python
async def human_click(
    page: Page,
    selector: Optional[str] = None,
    *,
    offset_range: int = 5,
    move_first: bool = True,
) -> None:
    """
    Click with human-like mouse movement and slight position offset.

    Args:
        page: Patchright Page object
        selector: Element selector
        offset_range: Maximum offset in pixels from center
        move_first: Whether to move mouse naturally before clicking
    """
```

### human_type()

```python
async def human_type(
    page: Page,
    text: str,
    selector: Optional[str] = None,
    *,
    min_delay_ms: int = 30,
    max_delay_ms: int = 150,
    mistake_probability: float = 0.02,
    think_pause_probability: float = 0.05,
) -> None:
    """
    Type text with human-like timing, including occasional mistakes.

    Args:
        page: Patchright Page object
        text: Text to type
        selector: Optional element selector to click first
        min_delay_ms: Minimum delay between keystrokes
        max_delay_ms: Maximum delay between keystrokes
        mistake_probability: Chance of making a typo (0-1)
        think_pause_probability: Chance of pausing to "think" (0-1)
    """
```

### human_scroll()

```python
async def human_scroll(
    page: Page,
    direction: str = "down",
    amount: Optional[int] = None,
    *,
    smooth: bool = True,
    duration: float = 0.5,
) -> None:
    """
    Scroll with human-like momentum and variable speed.

    Args:
        page: Patchright Page object
        direction: "up" or "down"
        amount: Pixels to scroll (random 200-600 if not specified)
        smooth: Whether to use smooth scrolling animation
        duration: Duration of smooth scroll in seconds
    """
```

### random_delay()

```python
async def random_delay(
    min_ms: int = 100,
    max_ms: int = 500,
) -> None:
    """
    Wait for a random duration.

    Args:
        min_ms: Minimum delay in milliseconds
        max_ms: Maximum delay in milliseconds
    """
```

### human_wait()

```python
async def human_wait(
    min_seconds: float = 0.5,
    max_seconds: float = 2.0,
) -> None:
    """
    Wait with human-like variability (Beta distribution).

    Args:
        min_seconds: Minimum wait time
        max_seconds: Maximum wait time
    """
```

### simulate_reading()

```python
async def simulate_reading(
    page: Page,
    min_seconds: float = 2.0,
    max_seconds: float = 8.0,
) -> None:
    """
    Simulate a user reading a page (scrolling, pausing).

    Args:
        page: Patchright Page object
        min_seconds: Minimum reading time
        max_seconds: Maximum reading time
    """
```

## TLS Fingerprinting (HTTP)

*Requires: `pip install abrasio[tls]`*

### StealthClient

```python
from abrasio.http import StealthClient, BrowserImpersonation

class StealthClient:
    """HTTP client with real browser TLS fingerprints via curl_cffi."""

    def __init__(
        self,
        impersonate: BrowserImpersonation = BrowserImpersonation.DEFAULT,
        proxy: Optional[str] = None,
        region: Optional[str] = None,
        rotate_impersonation: bool = False,
    ) -> None:
        """
        Args:
            impersonate: Browser to impersonate for TLS fingerprint
            proxy: Proxy URL
            region: Region for Accept-Language header
            rotate_impersonation: Rotate browser version on each request
        """

    async def get(self, url: str, **kwargs) -> StealthResponse: ...
    async def post(self, url: str, **kwargs) -> StealthResponse: ...

    # Context manager support
    async def __aenter__(self) -> "StealthClient": ...
    async def __aexit__(self, *args) -> None: ...
```

## Sync API

Synchronous wrapper for the async API. Compatible with Python 3.8+ including 3.10+.

```python
from abrasio.sync_api import Abrasio

class Abrasio:
    """Synchronous interface for Abrasio SDK."""

    def __init__(
        self,
        config: Optional[Union[AbrasioConfig, str]] = None,
        *,
        api_key: Optional[str] = None,
        headless: bool = True,
        proxy: Optional[str] = None,
        stealth: bool = True,
        **kwargs,
    ) -> None: ...

    def start(self) -> "Abrasio": ...
    def close(self) -> None: ...
    def new_page(self) -> Page: ...
    def new_context(self, **kwargs) -> BrowserContext: ...

    @property
    def browser(self): ...
    @property
    def is_cloud(self) -> bool: ...
    @property
    def is_local(self) -> bool: ...

    # Context manager support
    def __enter__(self) -> "Abrasio": ...
    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...
```

## Type Hints

```python
from typing import Optional, Dict, Any, List, Tuple, Union
from patchright.async_api import Page, BrowserContext

# Page from Patchright (same as Playwright)
# See: https://playwright.dev/python/docs/api/class-page
```
