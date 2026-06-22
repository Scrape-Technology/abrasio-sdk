"""Main Abrasio class - unified interface for local and cloud browsers."""

from typing import Optional, Union, Dict, TYPE_CHECKING
import logging

from ._config import AbrasioConfig
from ._exceptions import AbrasioError

if TYPE_CHECKING:
    from patchright.async_api import BrowserContext, Page

logger = logging.getLogger("abrasio")


class Abrasio:
    """
    Unified interface for stealth web scraping.

    Automatically selects between local (free) and cloud (paid) modes
    based on whether an API key is provided.

    Usage:
        # Local mode (free) - no API key
        async with Abrasio() as browser:
            page = await browser.new_page()
            await page.goto("https://example.com")

        # Cloud mode (paid) - with API key
        async with Abrasio(api_key="sk_live_xxx") as browser:
            page = await browser.new_page()
            await page.goto("https://example.com")

        # With config object
        config = AbrasioConfig(headless=False, locale="pt-BR")
        async with Abrasio(config) as browser:
            ...
    """

    def __init__(
        self,
        config: Optional[Union[AbrasioConfig, str]] = None,
        *,
        api_key: Optional[str] = None,
        headless: bool = True,
        proxy: Optional[Union[str, Dict[str, str]]] = None,
        stealth: bool = True,
        **kwargs,
    ):
        """
        Initialize Abrasio.

        Args:
            config: AbrasioConfig object or API key string
            api_key: Abrasio API key (enables cloud mode)
            headless: Run browser in headless mode
            proxy: Proxy URL for local mode
            stealth: Enable stealth patches
            **kwargs: Additional config options
        """
        # Handle different init patterns
        if isinstance(config, str):
            # Abrasio("sk_live_xxx") - API key passed as first arg
            api_key = config
            config = None

        if config is None:
            config = AbrasioConfig(
                api_key=api_key,
                headless=headless,
                proxy=proxy,
                stealth=stealth,
                **kwargs,
            )

        self.config = config
        self._browser = None
        self._playwright = None
        self._session = None  # For cloud mode

        # Log mode
        mode = "CLOUD" if self.config.is_cloud_mode else "LOCAL"
        logger.info(f"Abrasio initialized in {mode} mode")

    @property
    def is_cloud(self) -> bool:
        """Check if running in cloud mode."""
        return self.config.is_cloud_mode

    @property
    def is_local(self) -> bool:
        """Check if running in local mode."""
        return self.config.is_local_mode

    async def __aenter__(self) -> "Abrasio":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def start(self) -> "Abrasio":
        """
        Start the browser.

        Returns:
            self for chaining
        """
        if self.config.is_cloud_mode:
            await self._start_cloud()
        else:
            await self._start_local()
        return self

    async def _start_local(self) -> None:
        """Start local browser with stealth patches."""
        from .local.browser import StealthBrowser

        self._browser = StealthBrowser(self.config)
        await self._browser.start()
        logger.info("Local stealth browser started")

    async def _start_cloud(self) -> None:
        """Start cloud browser session."""
        from .cloud.browser import CloudBrowser

        self._browser = CloudBrowser(self.config)
        await self._browser.start()
        logger.info("Cloud browser session started")

    async def close(self) -> None:
        """Close the browser and cleanup resources."""
        if self._browser:
            try:
                await self._browser.close()
            finally:
                self._browser = None
        logger.info("Browser closed")

    async def new_page(self, **kwargs) -> "Page":
        """
        Create a new page.

        Args:
            **kwargs: Passed to new_context() when creating the page context
                      (e.g. ignore_https_errors=True). Ignored if the profile
                      context already exists and no kwargs are provided.

        Returns:
            Patchright Page object with stealth enhancements
        """
        if not self._browser:
            raise AbrasioError("Browser not started. Use 'async with Abrasio()' or call start() first.")
        return await self._browser.new_page(**kwargs)

    async def new_context(self, **kwargs) -> "BrowserContext":
        """
        Return a browser context.

        No kwargs → returns the profile context (contexts[0]) with extensions active.
        With kwargs (e.g. ignore_https_errors=True) → creates a new context passing
        the options directly to Patchright.

        Returns:
            Patchright BrowserContext object
        """
        if not self._browser:
            raise AbrasioError("Browser not started. Use 'async with Abrasio()' or call start() first.")
        return await self._browser.new_context(**kwargs)

    @property
    def browser(self):
        """Get the underlying browser or context object.

        In cloud mode: returns the Patchright Browser object.
        In local mode: returns the BrowserContext (persistent context has no separate Browser).
        """
        if not self._browser:
            raise AbrasioError("Browser not started.")
        if hasattr(self._browser, 'browser'):
            return self._browser.browser
        if hasattr(self._browser, 'context'):
            return self._browser.context
        raise AbrasioError("Browser object not available.")

    @property
    def live_view_url(self) -> Optional[str]:
        """Get the live view URL for real-time browser streaming (cloud mode only)."""
        if self._browser and hasattr(self._browser, 'live_view_url'):
            return self._browser.live_view_url
        return None
