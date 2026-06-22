"""Stealth browser implementation using Patchright for maximum anti-detection."""

import os
import tempfile
from typing import Optional, TYPE_CHECKING
import logging

from patchright.async_api import async_playwright, BrowserContext, Page

from .._config import AbrasioConfig

if TYPE_CHECKING:
    from patchright.async_api import Playwright

logger = logging.getLogger("abrasio.local")

# Canvas noise: adds subtle random noise to canvas pixel data reads.
# This makes the canvas fingerprint unique per session without breaking functionality.
_CANVAS_NOISE_SCRIPT = """
(() => {
    const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function(...args) {
        const imageData = originalGetImageData.apply(this, args);
        const data = imageData.data;
        for (let i = 0; i < data.length; i += 4) {
            // Add +-1 noise to RGB channels (imperceptible)
            data[i]     = data[i]     + (Math.random() < 0.5 ? -1 : 1) & 0xff;
            data[i + 1] = data[i + 1] + (Math.random() < 0.5 ? -1 : 1) & 0xff;
            data[i + 2] = data[i + 2] + (Math.random() < 0.5 ? -1 : 1) & 0xff;
        }
        return imageData;
    };
    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(...args) {
        const ctx = this.getContext('2d');
        if (ctx) {
            const imageData = ctx.getImageData(0, 0, this.width, this.height);
            ctx.putImageData(imageData, 0, 0);
        }
        return originalToDataURL.apply(this, args);
    };
    const originalToBlob = HTMLCanvasElement.prototype.toBlob;
    HTMLCanvasElement.prototype.toBlob = function(callback, ...args) {
        const ctx = this.getContext('2d');
        if (ctx) {
            const imageData = ctx.getImageData(0, 0, this.width, this.height);
            ctx.putImageData(imageData, 0, 0);
        }
        return originalToBlob.call(this, callback, ...args);
    };
})();
"""

# Audio noise: adds subtle noise to AudioContext fingerprint reads.
_AUDIO_NOISE_SCRIPT = """
(() => {
    const originalGetFloatFrequencyData = AnalyserNode.prototype.getFloatFrequencyData;
    AnalyserNode.prototype.getFloatFrequencyData = function(array) {
        originalGetFloatFrequencyData.call(this, array);
        for (let i = 0; i < array.length; i++) {
            array[i] += (Math.random() - 0.5) * 0.001;
        }
    };
    const originalGetChannelData = AudioBuffer.prototype.getChannelData;
    AudioBuffer.prototype.getChannelData = function(channel) {
        const data = originalGetChannelData.call(this, channel);
        for (let i = 0; i < data.length; i++) {
            data[i] += (Math.random() - 0.5) * 0.0001;
        }
        return data;
    };
})();
"""


class StealthBrowser:
    """
    Local browser with Patchright anti-detection patches.

    Patchright is an undetected Playwright fork that:
    - Avoids Runtime.enable CDP leak (executes JS in isolated ExecutionContexts)
    - Disables Console.enable to prevent serialization detection
    - Removes automation flags (--enable-automation, AutomationControlled)
    - Supports closed Shadow DOM interaction

    Best Practices for Maximum Stealth:
    - Uses launch_persistent_context instead of launch
    - Uses channel="chrome" for real Chrome (not Chromium)
    - Does NOT set custom user_agent (real browser fingerprint)
    - Uses no_viewport=True for realistic behavior
    """

    def __init__(self, config: AbrasioConfig):
        self.config = config
        self._playwright: Optional["Playwright"] = None
        self._context: Optional[BrowserContext] = None
        self._user_data_dir: Optional[str] = None

    @property
    def context(self) -> BrowserContext:
        """Get the browser context."""
        if not self._context:
            raise RuntimeError("Browser not started")
        return self._context

    async def start(self) -> None:
        """
        Start the browser with maximum stealth configuration.

        Uses launch_persistent_context which is more stealthy than
        regular launch + new_context because it:
        - Persists cookies and storage
        - Uses real browser profile structure
        - Avoids context creation fingerprints
        """
        self._playwright = await async_playwright().start()

        # Create persistent user data directory
        if self.config.user_data_dir:
            self._user_data_dir = self.config.user_data_dir
        else:
            # Create temp dir that persists for session
            self._user_data_dir = tempfile.mkdtemp(prefix="abrasio_profile_")

        # Build launch arguments for stealth
        args = self._get_stealth_args()

        # Proxy configuration
        proxy = None
        if self.config.proxy:
            if isinstance(self.config.proxy, dict):
                proxy = dict(self.config.proxy)
                server = proxy.get("server", "")
                if server and "://" not in server:
                    proxy["server"] = "http://" + server
            else:
                server = self.config.proxy
                if "://" not in server:
                    server = "http://" + server
                proxy = {"server": server}

        # Launch with persistent context for maximum stealth
        # Key: use channel="chrome" for real Chrome, not Chromium
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=self._user_data_dir,
            channel="chrome",  # Use real Chrome for better fingerprint
            headless=self.config.headless,
            args=args,
            proxy=proxy,
            # IMPORTANT: no_viewport=True for realistic behavior
            # Setting viewport can be detected as automation
            no_viewport=not self.config.viewport,
            viewport=self.config.viewport if self.config.viewport else None,
            # Locale and timezone (these are safe to set)
            #locale=self.config.locale,
            #timezone_id=self.config.timezone,
            # DO NOT set user_agent - let real Chrome handle it
            # Custom user_agent is easily detected via fingerprint mismatch
            ignore_default_args=[
                "--enable-automation",
                "--disable-extensions",
            ],
            # Permissions that real browsers have
            permissions=["geolocation", "notifications"],
            # TLS Client Authentication (e.g. ICP-Brasil certs for gov.br logins)
            client_certificates=self.config.client_certificates,
        )

        # Inject fingerprint noise scripts if configured
        await self._inject_fingerprint_noise()

        # Humanize all page interactions if requested
        if self.config.humanize:
            from ..human.actions import humanize_context
            await humanize_context(
                self._context,
                headless=self.config.headless,
                speed_factor=self.config.humanize_speed,
            )

        logger.info(f"Patchright browser started (headless={self.config.headless})")
        logger.debug(f"User data dir: {self._user_data_dir}")
        logger.debug(f"Launch args: {args}")

    async def close(self) -> None:
        """Close browser and cleanup."""
        # Use try/finally on each step so a failure in context.close() doesn't
        # prevent playwright.stop() from running (which would orphan the Chrome process).
        if self._context:
            try:
                await self._context.close()
            except Exception as e:
                logger.warning(f"Failed to close browser context: {e}")
            finally:
                self._context = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning(f"Failed to stop playwright: {e}")
            finally:
                self._playwright = None

        # Optionally cleanup temp user data dir
        if self._user_data_dir and self._user_data_dir.startswith(tempfile.gettempdir()):
            try:
                import shutil
                shutil.rmtree(self._user_data_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to cleanup user data dir: {e}")

    async def new_context(self, **kwargs) -> BrowserContext:
        """
        Get the browser context.

        Note: With persistent context, we return the main context.
        Creating multiple contexts reduces stealth as it's detectable.

        Args:
            **kwargs: Ignored for compatibility (persistent context is pre-configured)

        Returns:
            The main BrowserContext
        """
        if not self._context:
            raise RuntimeError("Browser not started")

        # With persistent context, we don't create new contexts
        # Multiple contexts are detectable and reduce stealth
        return self._context

    async def new_page(self) -> Page:
        """
        Create a new page.

        Returns:
            Page ready for navigation
        """
        if not self._context:
            raise RuntimeError("Browser not started")

        page = await self._context.new_page()
        return page

    def _get_stealth_args(self) -> list:
        """
        Get Chrome launch arguments for stealth.

        Patchright handles CDP-level patches (Runtime.enable leak, etc).
        We add Blink-level and UI flags that Patchright doesn't cover.
        """
        fp = self.config.fingerprint

        args = [
            # CRITICAL: prevents navigator.webdriver=true at the Blink level
            # Patchright patches CDP, but this flag patches the renderer itself
            "--disable-blink-features=AutomationControlled",

            # Suppress first-run dialogs
            "--no-first-run",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--no-default-browser-check",

            # Disable infobars (e.g. "Chrome is being controlled by automated software")
            "--disable-infobars",
            "--disable-popup-blocking",
            "--disable-component-update",
            "--disable-default-apps",

            # Window size (realistic desktop)
            #"--window-size=1920,1080",
        ]

        # Fix User-Agent in headless mode: Chrome adds "HeadlessChrome" which is detectable
        # We replace it with the normal Chrome UA to avoid detection
        # NOTE: We use a recent stable Chrome UA. The exact version doesn't matter much
        # as long as it's consistent with the installed Chrome (which Patchright uses).
        # The key is removing "HeadlessChrome" from the string.
        if self.config.headless:
            import platform

            # Detect OS and build appropriate User-Agent
            system = platform.system()
            if system == "Windows":
                # Windows 10/11 User-Agent
                user_agent = (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                )
            elif system == "Darwin":
                # macOS User-Agent
                user_agent = (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                )
            else:
                # Linux User-Agent
                user_agent = (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                )

            args.append(f"--user-agent={user_agent}")
            logger.debug(f"Headless mode: overriding User-Agent to hide HeadlessChrome ({system})")

        #WebGL: only add flags when DISABLING (enabled by default in Chrome)
        if not fp.webgl:
            args.extend(["--disable-webgl", "--disable-webgl2"])
            logger.debug("WebGL disabled by fingerprint config")

        # WebRTC: block IP leak when disabled (important with proxy)
        if not fp.webrtc:
            args.append("--enforce-webrtc-ip-permission-check")
            args.append("--disable-webrtc-multiple-routes")
            args.append("--disable-webrtc-hw-encoding")
            logger.debug("WebRTC IP leak protection enabled by fingerprint config")

        # Add user-specified extra args
        if hasattr(self.config, 'extra_args') and self.config.extra_args:
            args.extend(self.config.extra_args)

        return args

    async def _inject_fingerprint_noise(self) -> None:
        """Inject canvas/audio noise scripts if configured."""
        fp = self.config.fingerprint

        if fp.canvas_noise:
            await self._context.add_init_script(script=_CANVAS_NOISE_SCRIPT)
            logger.debug("Canvas noise injection enabled")

        if fp.audio_noise:
            await self._context.add_init_script(script=_AUDIO_NOISE_SCRIPT)
            logger.debug("Audio noise injection enabled")
