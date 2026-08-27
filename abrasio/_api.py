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

    async def route_with_certificate(
        self,
        target,
        url,
        certificate: Dict,
        *,
        proxy: Optional[Union[str, Dict[str, str]]] = None,
        timeout: Optional[float] = None,
        retries: int = 2,
        retry_backoff: float = 1.0,
    ) -> None:
        """
        Intercept `url` on `target` (a Page or BrowserContext) and replay it using
        a TLS client certificate.

        **Cloud mode**: delegates to the Abrasio API relay endpoint
        (`POST /v1/browser/session/{id}/certificate-fetch`). The relay executes the
        mTLS request from within the session's region/proxy — no proxy configuration
        needed by the caller, and no proxy credentials are ever exposed to the SDK.

        **Local mode**: replays via Patchright's own `APIRequestContext`. Pass `proxy`
        to route through a specific exit IP when the driver process is outside the
        target country.

        Args:
            target: Page or BrowserContext to intercept requests on.
            url: URL/glob pattern to intercept, as accepted by Playwright's `route()`.
            certificate: A dict built with `abrasio.build_client_certificate(...)`.
            proxy: Proxy for local-mode replay only. Ignored in cloud mode.
            timeout: Request timeout in seconds. Defaults to the session's configured
                `timeout` (`AbrasioConfig.timeout`, in ms).
            retries: Extra attempts if the replay raises. Default 2 (3 total).
            retry_backoff: Seconds to wait before each retry × attempt. Default 1.0.
        """
        from .utils.certificates import route_with_client_certificate

        if not self._browser:
            raise AbrasioError("Browser not started. Call start() first.")

        _timeout = timeout if timeout is not None else self.config.timeout / 1000

        if hasattr(self._browser, "relay_certificate_fetch"):
            # Cloud mode: mTLS request runs server-side (in session's region).
            _relay = self._browser.relay_certificate_fetch
            await route_with_client_certificate(
                target, url, certificate,
                relay_fn=_relay,
                timeout=_timeout,
                retries=retries,
                retry_backoff=retry_backoff,
            )
        else:
            # Local mode: replay via local APIRequestContext.
            if not self._browser._playwright:
                raise AbrasioError("Browser not started. Call start() first.")
            await route_with_client_certificate(
                target, url, certificate,
                playwright_instance=self._browser._playwright,
                proxy=proxy,
                timeout=_timeout,
                retries=retries,
                retry_backoff=retry_backoff,
            )

    async def get_artifacts(self):
        """
        List files downloaded by the browser during this session (cloud mode only),
        each with a presigned S3 URL valid for ~1h.

        Returns:
            List of {filename, size, download_url, created_at}
        """
        if not self._browser or not hasattr(self._browser, "get_artifacts"):
            raise AbrasioError("get_artifacts() is only available in cloud mode.")
        return await self._browser.get_artifacts()

    @property
    def live_view_url(self) -> Optional[str]:
        """Get the live view URL for real-time browser streaming (cloud mode only)."""
        if self._browser and hasattr(self._browser, 'live_view_url'):
            return self._browser.live_view_url
        return None
