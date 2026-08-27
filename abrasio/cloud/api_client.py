"""HTTP client for Abrasio API."""

from typing import Optional, Dict, Any, Tuple
import base64
import logging
import asyncio
import time
import uuid

import httpx

from .._config import AbrasioConfig
from .._exceptions import (
    AuthenticationError,
    SessionError,
    InsufficientFundsError,
    RateLimitError,
    TimeoutError,
    AbrasioError,
)

logger = logging.getLogger("abrasio.cloud.api")

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0  # seconds
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


class AbrasioAPIClient:
    """
    HTTP client for communicating with Abrasio API.

    Handles:
    - Session creation
    - Session status polling
    - Session termination
    - Error handling with automatic retry
    """

    def __init__(self, config: AbrasioConfig):
        self.config = config
        self.base_url = config.api_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "AbrasioAPIClient":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def start(self) -> None:
        """Initialize HTTP client."""
        if not self.config.api_key:
            raise AbrasioError("API key is required. Set ABRASIO_API_KEY or pass api_key to config.")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "X-API-KEY": self.config.api_key,
                "Content-Type": "application/json",
                "User-Agent": "abrasio-sdk-python/0.1.0",
            },
            timeout=httpx.Timeout(30.0),
        )

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure client is initialized."""
        if not self._client:
            raise AbrasioError("API client not started. Call start() first.")
        return self._client

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request with automatic retry on transient errors.

        Retries on 429 (rate limit), 502, 503, 504 with exponential backoff.
        Respects Retry-After header when present.
        """
        client = self._ensure_client()
        last_exception = None

        # Add request tracing header
        headers = kwargs.pop("headers", {})
        headers["X-Request-ID"] = str(uuid.uuid4())
        kwargs["headers"] = headers

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await getattr(client, method)(path, **kwargs)

                if response.status_code not in RETRYABLE_STATUS_CODES:
                    return self._handle_response(response)

                # Retryable status - calculate wait time
                if attempt == MAX_RETRIES:
                    return self._handle_response(response)

                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    wait = min(float(retry_after), 30.0)
                else:
                    wait = min(RETRY_BACKOFF_BASE * (2 ** attempt), 15.0)

                logger.warning(
                    f"Request to {path} returned {response.status_code}, "
                    f"retrying in {wait:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})"
                )
                await asyncio.sleep(wait)

            except httpx.TimeoutException:
                last_exception = TimeoutError(f"Request to {path} timed out")
                if attempt == MAX_RETRIES:
                    raise last_exception

                wait = min(RETRY_BACKOFF_BASE * (2 ** attempt), 15.0)
                logger.warning(
                    f"Request to {path} timed out, "
                    f"retrying in {wait:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})"
                )
                await asyncio.sleep(wait)

        raise last_exception or AbrasioError("Request failed after retries")

    async def create_session(
        self,
        url: str = None,
        region: Optional[str] = None,
        profile_id: Optional[str] = None,
        device: str = "desktop",
        mobile_model: Optional[str] = None,
        proxy: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Create a new browser session.

        Args:
            url: Target URL for region inference
            region: Target region (e.g., "BR", "US")
            profile_id: Persistent profile ID to use
            device: "desktop" or "mobile"
            mobile_model: Mobile preset name (e.g. "pixel-8", "iphone-15")
            proxy: Proxy override — string "http://host:port" or dict
                   {"server": "...", "username": "...", "password": "..."}.
                   Overrides the proxy stored in the selected profile's meta.json.

        Returns:
            Session data including session_id

        Raises:
            AuthenticationError: Invalid API key
            InsufficientFundsError: Not enough balance
            SessionError: Session creation failed
        """
        payload = {}
        if url:
            payload["url"] = url
        else:
            payload["url"] = "https://example.com"
        if region:
            payload["region"] = region
        if profile_id:
            payload["profile_id"] = profile_id
        if device and device != "desktop":
            payload["device"] = device
        if mobile_model:
            payload["mobile_model"] = mobile_model
        if proxy:
            if isinstance(proxy, dict):
                proxy_normalized = dict(proxy)
                server = proxy_normalized.get("server", "")
                if server and "://" not in server:
                    proxy_normalized["server"] = "http://" + server
                payload["proxy"] = proxy_normalized
            else:
                server = proxy if "://" in proxy else "http://" + proxy
                payload["proxy"] = {"server": server}

        return await self._request_with_retry("post", "/v1/browser/session/", json=payload)

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """
        Get session status.

        Args:
            session_id: Session ID

        Returns:
            Session data including status and ws_endpoint

        Raises:
            SessionError: Session not found
        """
        return await self._request_with_retry("get", f"/v1/browser/session/{session_id}")

    async def wait_for_ready(
        self,
        session_id: str,
        timeout_seconds: int = 60,
        poll_interval: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Wait for session to be ready.

        Polls the session status until it's READY or fails.

        Args:
            session_id: Session ID
            timeout_seconds: Maximum time to wait
            poll_interval: Time between polls

        Returns:
            Session data with ws_endpoint

        Raises:
            TimeoutError: Session didn't become ready in time
            SessionError: Session failed
        """
        # Bug fix: this used to track "elapsed" by counting loop iterations
        # (`elapsed += poll_interval`) rather than real time. get_session()
        # has its own retry-with-backoff (up to ~3 retries, tens of seconds
        # each on 429/502/503/504), so a single slow iteration could burn far
        # more than poll_interval seconds while only ever counting as one —
        # letting the real wait balloon to many times timeout_seconds, or
        # never time out at all under sustained API flakiness. Track real
        # wall-clock time instead, and bound each get_session() call to
        # whatever time remains so the total can't overrun the budget either.
        deadline = time.monotonic() + timeout_seconds

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            try:
                session = await asyncio.wait_for(self.get_session(session_id), timeout=remaining)
            except asyncio.TimeoutError:
                break

            status = session.get("status")

            if status == "READY":
                logger.info(f"Session {session_id} is ready")
                return session

            if status in ("FAILED", "ERROR"):
                error_msg = session.get("error_message", "Unknown error")
                raise SessionError(f"Session failed: {error_msg}", session_id)

            if status == "FINISHED":
                raise SessionError("Session already finished", session_id)

            logger.debug(f"Session {session_id} status: {status}, waiting...")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            await asyncio.sleep(min(poll_interval, remaining))

        raise TimeoutError(
            f"Session {session_id} did not become ready within {timeout_seconds}s",
            timeout_seconds * 1000,
        )

    async def certificate_fetch(
        self,
        session_id: str,
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
        Execute an mTLS request via the session's certificate-fetch relay endpoint.

        The Abrasio worker makes the request from within the session's region/proxy,
        so geo-restricted endpoints are reachable without exposing any proxy config.

        Request schema:
            POST /v1/browser/session/{id}/certificate-fetch
            {
                "url": "https://...",
                "method": "POST",
                "headers": {...},
                "body": "<base64>",            # optional
                "timeout_ms": 60000,
                "max_redirects": 0,
                "certificate": {
                    "origin": "https://...",
                    "cert_pem": "<base64>",
                    "key_pem": "<base64>"
                }
            }

        Response schema:
            {
                "status": 302,
                "headers": {"location": "...", ...},
                "body": "<base64>"
            }

        Returns:
            (status_code, response_headers, response_body_bytes)
        """
        payload: Dict[str, Any] = {
            "url": url,
            "method": method.upper(),
            "headers": headers,
            "timeout_ms": int(timeout * 1000),
            "max_redirects": 0,
            "certificate": {
                "origin": origin,
                "cert_pem": base64.b64encode(cert_pem).decode(),
                "key_pem": base64.b64encode(key_pem).decode(),
            },
        }
        if body:
            payload["body"] = base64.b64encode(body).decode()

        data = await self._request_with_retry(
            "post",
            f"/v1/browser/session/{session_id}/certificate-fetch",
            json=payload,
        )

        status: int = data["status"]
        resp_headers: Dict[str, str] = data.get("headers", {})
        body_b64: str = data.get("body", "")
        resp_body: bytes = base64.b64decode(body_b64) if body_b64 else b""
        return status, resp_headers, resp_body

    async def finish_session(self, session_id: str) -> Dict[str, Any]:
        """
        Finish/close a session.

        Args:
            session_id: Session ID

        Returns:
            Final session data
        """
        return await self._request_with_retry("post", f"/v1/browser/session/{session_id}/finish")

    async def cancel_session(self, session_id: str) -> Dict[str, Any]:
        """
        Cancel a session. Works for sessions in any active state (PENDING, READY, RUNNING).

        This signals the worker to stop the session and triggers final billing.

        Args:
            session_id: Session ID

        Returns:
            Final session data

        Raises:
            SessionError: Session not found or already finished
        """
        return await self._request_with_retry("post", f"/v1/browser/session/{session_id}/finish")

    async def get_session_artifacts(self, session_id: str) -> Any:
        """
        List files downloaded by the browser during this session.

        Each entry has a presigned S3 URL (valid ~1h) the caller can fetch
        directly — no further Abrasio API calls needed to get the bytes.

        Args:
            session_id: Session ID

        Returns:
            List of {filename, size, download_url, created_at}

        Raises:
            SessionError: Session not found or not owned by this API key
        """
        return await self._request_with_retry(
            "get", f"/v1/browser/session/{session_id}/artifacts"
        )

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle API response and raise appropriate exceptions."""
        if response.status_code == 200:
            return response.json()

        if response.status_code == 401:
            raise AuthenticationError()

        if response.status_code == 402:
            # Insufficient funds
            data = response.json()
            balance = data.get("balance")
            raise InsufficientFundsError(balance)

        if response.status_code == 429:
            # Rate limit
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(int(retry_after) if retry_after else None)

        if response.status_code == 404:
            raise SessionError("Session not found")

        # Generic error
        try:
            data = response.json()
            detail = data.get("detail", "Unknown error")
        except Exception:
            detail = response.text

        raise AbrasioError(f"API error ({response.status_code}): {detail}")
