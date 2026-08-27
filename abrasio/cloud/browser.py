"""Cloud browser implementation using Abrasio API with Patchright."""

from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING
from urllib.parse import urlsplit
import asyncio
import ipaddress
import logging

from patchright.async_api import async_playwright, Browser, BrowserContext, Page

from .._config import AbrasioConfig
from .._exceptions import AbrasioError, SessionError
from .api_client import AbrasioAPIClient

if TYPE_CHECKING:
    from patchright.async_api import Playwright

logger = logging.getLogger("abrasio.cloud")

# RFC 6598 Shared Address Space (CGNAT). Not publicly routable, but Python's
# ipaddress.is_private doesn't flag it (confirmed unflagged through 3.14) —
# check it explicitly alongside the standard private/reserved ranges.
_CGNAT_RANGE = ipaddress.ip_network("100.64.0.0/10")


def _assert_routable_ws_endpoint(ws_endpoint: str, session_id: Optional[str]) -> None:
    """
    Reject ws_endpoint hosts that can never be reachable over the public internet.

    A legitimate Abrasio session always returns a publicly routable host. Seeing a
    private/CGNAT/loopback/link-local IP here means the response didn't come from
    our API at all (e.g. a transparent proxy or cache on the client's network
    intercepted/fabricated it) — fail fast with a clear message instead of hanging
    until the OS connect timeout (which can take minutes).
    """
    host = urlsplit(ws_endpoint).hostname
    if not host:
        return
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return  # Hostname, not a literal IP — DNS will resolve it normally.

    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified or ip in _CGNAT_RANGE:
        raise SessionError(
            f"Received a non-routable WebSocket endpoint ({ws_endpoint}). "
            "This usually means a proxy, firewall, or cache on your network "
            "intercepted the connection to the Abrasio API instead of forwarding "
            "it — this response did not originate from Abrasio. Check your "
            "network's outbound HTTPS path to the Abrasio API.",
            session_id,
        )


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
                device=self.config.device,
                mobile_model=self.config.mobile_model,
                proxy=self.config.proxy,  # Override profile's stored proxy (if provided)
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

            #_assert_routable_ws_endpoint(self._ws_endpoint, self._session_id)

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

            # Humanize all page interactions if requested
            if self.config.humanize:
                from ..human.actions import humanize_context
                contexts = self._browser.contexts
                if contexts:
                    await humanize_context(
                        contexts[0],
                        headless=self.config.headless,
                        speed_factor=self.config.humanize_speed,
                    )

            logger.info("Connected to cloud browser")
        except Exception:
            # Cleanup on failure to prevent resource leaks
            await self.close()
            raise

    async def close(self) -> None:
        """Close browser and cleanup session.

        Order matters: finish_session() is called BEFORE closing the CDP
        connection so the worker receives the FINISHING signal while the
        connection is still alive. Closing CDP first would leave the worker
        running until max-duration timeout if the signal never arrives.
        """
        # 1. Signal worker to stop BEFORE dropping the CDP connection.
        if self._api_client and self._session_id:
            try:
                await asyncio.wait_for(
                    self._api_client.finish_session(self._session_id),
                    timeout=5.0,
                )
                logger.info(f"Session {self._session_id} finished")
            except Exception as e:
                logger.warning(f"Failed to finish session: {e}")

        # 2. Now safely drop the CDP connection.
        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.warning(f"Failed to close browser connection: {e}")
            finally:
                self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning(f"Failed to stop playwright: {e}")
            finally:
                self._playwright = None

        if self._api_client:
            try:
                await self._api_client.close()
            except Exception as e:
                logger.warning(f"Failed to close API client: {e}")
            finally:
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

    async def relay_certificate_fetch(
        self,
        cert_pem: bytes,
        key_pem: bytes,
        origin: str,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Optional[bytes],
        timeout: float,
    ) -> Tuple[int, Dict[str, str], bytes]:
        """
        Execute an mTLS request via the Abrasio API relay endpoint.

        The relay runs inside the Abrasio infrastructure (same region/proxy as the
        browser session), so geo-restricted endpoints like certificado.sso.acesso.gov.br
        are reachable without the client configuring a proxy.

        Returns (status_code, response_headers, response_body).
        Raises AbrasioError / SessionError on failure.
        """
        if not self._api_client or not self._session_id:
            raise RuntimeError("Browser not started or session not active")
        return await self._api_client.certificate_fetch(
            session_id=self._session_id,
            cert_pem=cert_pem,
            key_pem=key_pem,
            origin=origin,
            method=method,
            url=url,
            headers=headers,
            body=body,
            timeout=timeout,
        )

    async def get_artifacts(self) -> Any:
        """
        List files downloaded by the browser during this session, each with
        a presigned S3 URL to fetch the bytes directly.

        Returns:
            List of {filename, size, download_url, created_at}
        """
        if not self._api_client or not self._session_id:
            raise RuntimeError("Browser not started or session not active")
        return await self._api_client.get_session_artifacts(self._session_id)

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
