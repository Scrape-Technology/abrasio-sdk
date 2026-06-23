"""Configuration for Abrasio SDK."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union
import os
import logging

logger = logging.getLogger("abrasio.config")


@dataclass
class FingerprintConfig:
    """
    Fingerprint protection settings (local mode only).

    In cloud mode, the cloud browser handles all
    fingerprinting with real collected fingerprints. These settings are
    completely ignored when using an API key.

    Attributes:
        webgl: Enable WebGL APIs (True=realistic, False=block).
            Blocking WebGL is a strong anti-bot signal. Only disable if
            you specifically need to hide GPU info.
        webrtc: Enable WebRTC (True=allow, False=block IP leak).
            Recommended False when using a proxy to prevent real IP leaks.
        canvas_noise: Add noise to canvas fingerprint reads.
            Makes canvas fingerprint unique per session.
        audio_noise: Add noise to AudioContext fingerprint reads.
            Makes audio fingerprint unique per session.
    """
    webgl: bool = True
    webrtc: bool = True
    canvas_noise: bool = False
    audio_noise: bool = False


@dataclass
class AbrasioConfig:
    """
    Configuration for Abrasio browser.

    Uses Patchright for maximum anti-detection. Key recommendations:
    - Don't set custom user_agent (creates fingerprint mismatch)
    - Don't set viewport (use no_viewport for realistic behavior)
    - Use user_data_dir for persistent profiles
    - Set region to auto-configure locale/timezone consistently

    Auto-Configuration Behavior:
    - **Cloud mode** (api_key set): Locale/timezone NOT set by SDK.
      The cloud browser automatically configures these based on proxy location.
    - **Local mode** (no api_key): Locale/timezone auto-detected from your public IP.
      This ensures browser settings match your actual location for better stealth.

    Attributes:
        api_key: Abrasio API key for cloud mode. If None, uses local mode.
        api_url: Abrasio API URL (default: https://abrasio-api.scrapetechnology.com)
        headless: Run browser in headless mode (default: True)
        proxy: Proxy URL for local mode (e.g., "http://user:pass@host:port")
        timeout: Default timeout in milliseconds (default: 30000)
        stealth: Enable stealth mode patches (default: True)
        locale: Browser locale (auto-detected from IP in local mode)
        timezone: Browser timezone (auto-detected from IP in local mode)
        user_agent: DEPRECATED - Don't use with Patchright
        viewport: Browser viewport (None = no_viewport for better stealth)
        user_data_dir: Persistent profile directory for local mode
        region: Target region for geo-targeting (e.g., "BR", "US"). Auto-configures locale/timezone.
        profile_id: Persistent profile ID for cloud mode
        auto_configure_region: Auto-configure locale/timezone from region/IP (default: True)
        extra_args: Extra browser launch arguments
        humanize: Humanize all browser interactions (mouse, keyboard, scroll). Default: False.
        humanize_speed: Speed multiplier for humanized interactions (1.0 = normal). Default: 1.0.
        client_certificates: TLS client certificates for sites requiring client-cert auth
            (e.g. ICP-Brasil logins on gov.br). Build entries with
            `abrasio.build_client_certificate(...)`. **Local mode only** — Playwright applies
            this via a local SOCKS proxy that the browser must dial back into, which only
            works when the browser runs on the same machine as the driver. In cloud mode
            (remote browser), use `Abrasio.route_with_certificate(...)` instead, which
            intercepts and replays the specific request outside the browser.
    """

    # Core settings
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("ABRASIO_API_KEY"))
    api_url: str = field(default_factory=lambda: os.getenv("ABRASIO_API_URL", "https://abrasio-api.scrapetechnology.com"))
    url: Optional[str] = None

    # Browser settings
    headless: bool = True
    proxy: Optional[Union[str, Dict[str, str]]] = None  # "http://host:port" or {"server":..., "username":..., "password":...}
    timeout: int = 30000

    # Stealth settings (local mode)
    stealth: bool = True
    locale: Optional[str] = None  # Auto-configured from region
    timezone: Optional[str] = None  # Auto-configured from region
    user_agent: Optional[str] = None  # DEPRECATED: Don't set custom UA with Patchright
    viewport: Optional[Dict[str, int]] = None  # None = no_viewport for better stealth
    user_data_dir: Optional[str] = None  # Persistent profile directory

    # Cloud settings (paid mode)
    region: Optional[str] = None
    profile_id: Optional[str] = None
    device: str = "desktop"          # "desktop" | "mobile"
    mobile_model: Optional[str] = None  # e.g. "pixel-8", "iphone-15" (used when device="mobile")

    # Region auto-configuration
    auto_configure_region: bool = True  # Auto-configure locale/timezone from region

    # Fingerprint protection (local mode only - ignored in cloud mode)
    fingerprint: FingerprintConfig = field(default_factory=FingerprintConfig)

    # TLS Client Authentication: list of dicts built by build_client_certificate(),
    # e.g. [{"origin": "https://sso.acesso.gov.br", "pfxPath": "...", "passphrase": "..."}]
    # repr=False to avoid leaking cert/key bytes or passphrases in logs.
    client_certificates: Optional[List[Dict[str, Any]]] = field(default=None, repr=False)

    # Advanced
    extra_args: List[str] = field(default_factory=list)
    debug: bool = False

    # Humanization
    humanize: bool = False
    humanize_speed: float = 1.0

    # Internal: stores validation warnings
    _region_warnings: List[str] = field(default_factory=list, repr=False)

    def __post_init__(self):
        """Auto-configure and validate region settings after initialization."""
        # Cloud mode: Don't set locale/timezone, the cloud browser handles this
        if self.is_cloud_mode:
            logger.debug("Cloud mode detected. Locale/timezone will be set by cloud browser.")
            return

        # Local mode: Auto-detect from IP if not explicitly configured
        if self.region and self.auto_configure_region:
            self._auto_configure_from_region()
        elif self.region:
            self._validate_region_consistency()
        elif self.locale is None and self.timezone is None and self.auto_configure_region:
            # No region set - auto-detect from IP
            self._auto_configure_from_ip()

        # Set defaults if still not configured
        if self.locale is None:
            self.locale = "en-US"
        if self.timezone is None:
            self.timezone = "America/New_York"

    def _auto_configure_from_ip(self):
        """Auto-configure locale and timezone from public IP address."""
        try:
            from .utils.geolocation import get_locale_timezone_from_ip

            locale, timezone, country_code = get_locale_timezone_from_ip()

            self.locale = locale
            self.timezone = timezone
            self.region = country_code  # Also set region for consistency

            logger.info(f"Auto-configured from IP: locale={locale}, timezone={timezone}, region={country_code}")

        except Exception as e:
            logger.warning(f"Could not auto-configure from IP: {e}. Using defaults.")

    def _auto_configure_from_region(self):
        """Auto-configure locale and timezone from region."""
        try:
            from .utils.fingerprint import auto_configure_region, REGION_CONFIG

            if self.region.upper() not in REGION_CONFIG:
                logger.warning(f"Unknown region '{self.region}'. Using defaults.")
                return

            final_locale, final_timezone, warnings = auto_configure_region(
                region=self.region,
                locale=self.locale,
                timezone=self.timezone,
            )

            # Only override if not explicitly set
            if self.locale is None:
                self.locale = final_locale
                logger.debug(f"Auto-configured locale: {self.locale}")

            if self.timezone is None:
                self.timezone = final_timezone
                logger.debug(f"Auto-configured timezone: {self.timezone}")

            self._region_warnings = warnings

            # Log warnings
            for warning in warnings:
                logger.warning(f"Region consistency: {warning}")

        except ImportError:
            # utils module not available yet during import
            pass

    def _validate_region_consistency(self):
        """Validate region, locale, and timezone consistency."""
        try:
            from .utils.fingerprint import validate_region_consistency

            warnings = validate_region_consistency(
                region=self.region,
                locale=self.locale,
                timezone=self.timezone,
            )

            self._region_warnings = warnings

            for warning in warnings:
                logger.warning(f"Region consistency: {warning}")

        except ImportError:
            pass

    @property
    def region_warnings(self) -> List[str]:
        """Get any region consistency warnings."""
        return self._region_warnings.copy()

    @property
    def is_cloud_mode(self) -> bool:
        """Check if running in cloud mode (has API key)."""
        return self.api_key is not None and self.api_key.startswith("abr_")

    @property
    def is_local_mode(self) -> bool:
        """Check if running in local mode (no API key)."""
        return not self.is_cloud_mode

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "api_key": self.api_key,
            "api_url": self.api_url,
            "headless": self.headless,
            "proxy": self.proxy,
            "timeout": self.timeout,
            "stealth": self.stealth,
            "locale": self.locale,
            "timezone": self.timezone,
            "user_agent": self.user_agent,
            "viewport": self.viewport,
            "user_data_dir": self.user_data_dir,
            "region": self.region,
            "profile_id": self.profile_id,
            "fingerprint": {
                "webgl": self.fingerprint.webgl,
                "webrtc": self.fingerprint.webrtc,
                "canvas_noise": self.fingerprint.canvas_noise,
                "audio_noise": self.fingerprint.audio_noise,
            },
            "extra_args": self.extra_args,
            "debug": self.debug,
        }
