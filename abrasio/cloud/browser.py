"""Cloud browser implementation using Abrasio API with Patchright."""

from typing import Optional, TYPE_CHECKING
import logging

from patchright.async_api import async_playwright, Browser, BrowserContext, Page

from .._config import AbrasioConfig
from .._exceptions import AbrasioError, SessionError
from .api_client import AbrasioAPIClient

if TYPE_CHECKING:
    from patchright.async_api import Playwright

logger = logging.getLogger("abrasio.cloud")


class CloudBrowser:
    """
    Cloud browser connected to Abrasio infrastructure.

    Uses Patchright for CDP connection to maintain stealth even
    when connecting to remote browsers.

    Features:
    - Real collected fingerprints
    - Residential/datacenter IPs
    - Geo-targeting
    - Persistent profiles
    - Pay-per-use billing
    """

    def __init__(self, config: AbrasioConfig):
        self.config = config
        self._api_client: Optional[AbrasioAPIClient] = None
        self._playwright: Optional["Playwright"] = None
        self._browser: Optional[Browser] = None
        self._session_id: Optional[str] = None
        self._ws_endpoint: Optional[str] = None
        self._live_view_url: Optional[str] = None

    @property
    def browser(self) -> Browser:
        """Get the underlying Patchright browser."""
        if not self._browser:
            raise RuntimeError("Browser not connected")
        return self._browser

    @property
    def session_id(self) -> Optional[str]:
        """Get the current session ID."""
        return self._session_id

    @property
    def live_view_url(self) -> Optional[str]:
        """Get the live view URL for real-time browser streaming."""
        return self._live_view_url

    async def start(self) -> None:
        """
        Start cloud browser session.

        1. Create session via API
        2. Wait for session to be ready
        3. Connect to browser via WebSocket CDP (using Patchright)
        """
        # Initialize API client
        self._api_client = AbrasioAPIClient(self.config)
        await self._api_client.start()

        try:
            # Create session
            logger.info("Creating cloud browser session...")
            session_data = await self._api_client.create_session(
                url=self.config.url,  # Default URL for session creation
                region=self.config.region,
                profile_id=self.config.profile_id,
            )

            self._session_id = session_data.get("id")
            if not self._session_id:
                raise SessionError("No session ID returned from API")

            logger.info(f"Session created: {self._session_id}")

            # Wait for session to be ready
            session = await self._api_client.wait_for_ready(
                self._session_id,
                timeout_seconds=60,
            )

            self._ws_endpoint = session.get("ws_endpoint")
            if not self._ws_endpoint:
                raise SessionError("No WebSocket endpoint returned", self._session_id)

            # Show live view URL if available
            live_view_url = session.get("live_view_url")
            if live_view_url:
                self._live_view_url = live_view_url
                print(f"\n[Abrasio] Live View: {live_view_url}\n")
                logger.info(f"Live view available: {live_view_url}")

            logger.info(f"Connecting to WebSocket: {self._ws_endpoint}")

            # Connect via Patchright CDP (maintains stealth properties)
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.connect_over_cdp(self._ws_endpoint)

            logger.info("Connected to cloud browser")
        except Exception:
            # Cleanup on failure to prevent resource leaks
            await self.close()
            raise

    async def close(self) -> None:
        """Close browser and cleanup session."""
        # Close browser connection
        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        # Notify API that session is finished
        if self._api_client and self._session_id:
            try:
                await self._api_client.finish_session(self._session_id)
                logger.info(f"Session {self._session_id} finished")
            except Exception as e:
                logger.warning(f"Failed to finish session: {e}")

        if self._api_client:
            await self._api_client.close()
            self._api_client = None

        self._session_id = None
        self._ws_endpoint = None

    async def new_context(self, **kwargs) -> BrowserContext:
        """
        Create a new browser context.

        Note: In cloud mode, context options may be limited as the
        browser is pre-configured with specific fingerprints.

        Args:
            **kwargs: Patchright context options (may be ignored)

        Returns:
            BrowserContext
        """
        if not self._browser:
            raise RuntimeError("Browser not connected")

        # For cloud browsers, we typically use the default context
        # that's pre-configured with the fingerprint
        contexts = self._browser.contexts
        if contexts:
            return contexts[0]

        return await self._browser.new_context(**kwargs)

    async def new_page(self) -> Page:
        """
        Create a new page.

        Returns:
            Page connected to cloud browser
        """
        if not self._browser:
            raise RuntimeError("Browser not connected")

        # Get or create context
        contexts = self._browser.contexts
        if contexts:
            context = contexts[0]
        else:
            context = await self._browser.new_context()

        page = await context.new_page()
        return page
