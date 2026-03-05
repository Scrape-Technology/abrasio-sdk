"""Synchronous wrapper for Abrasio SDK."""

import asyncio
import threading
from typing import Optional, Union, TYPE_CHECKING

from .._api import Abrasio as AsyncAbrasio
from .._config import AbrasioConfig

if TYPE_CHECKING:
    from patchright.async_api import Browser, BrowserContext, Page


class SyncPage:
    """
    Synchronous wrapper around an async Patchright Page.

    Proxies all attribute accesses: coroutine methods are run on the
    browser's persistent event loop; non-coroutine attributes are
    returned as-is.
    """

    def __init__(self, async_page, run_fn):
        object.__setattr__(self, "_async_page", async_page)
        object.__setattr__(self, "_run", run_fn)

    def __getattr__(self, name):
        attr = getattr(object.__getattribute__(self, "_async_page"), name)
        run = object.__getattribute__(self, "_run")
        if asyncio.iscoroutinefunction(attr):
            def wrapper(*args, **kwargs):
                return run(attr(*args, **kwargs))
            return wrapper
        return attr

    def __repr__(self):
        return f"SyncPage({object.__getattribute__(self, '_async_page')!r})"


class Abrasio:
    """
    Synchronous interface for Abrasio SDK.

    Runs a single background event loop for the entire browser lifetime so
    that all Playwright/Patchright objects (context, pages, etc.) share the
    same loop — which is required for them to function correctly.

    Usage:
        with Abrasio() as browser:
            page = browser.new_page()
            page.goto("https://example.com")
            print(page.title())
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
    ):
        self._async_abrasio = AsyncAbrasio(
            config=config,
            api_key=api_key,
            headless=headless,
            proxy=proxy,
            stealth=stealth,
            **kwargs,
        )
        # Single persistent event loop shared across all operations
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, daemon=True, name="abrasio-event-loop"
        )
        self._thread.start()

    def _run(self, coro):
        """Submit a coroutine to the persistent loop and block until done."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=300)

    def _stop_loop(self):
        """Stop the background event loop and wait for the thread to exit."""
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=10)

    def __enter__(self) -> "Abrasio":
        """Context manager entry."""
        self._run(self._async_abrasio.start())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        try:
            self._run(self._async_abrasio.close())
        finally:
            self._stop_loop()

    def start(self) -> "Abrasio":
        """Start the browser."""
        self._run(self._async_abrasio.start())
        return self

    def close(self) -> None:
        """Close the browser."""
        try:
            self._run(self._async_abrasio.close())
        finally:
            self._stop_loop()

    def new_page(self) -> "SyncPage":
        """Create a new page."""
        async_page = self._run(self._async_abrasio.new_page())
        return SyncPage(async_page, self._run)

    def new_context(self, **kwargs) -> "BrowserContext":
        """Create a new browser context."""
        return self._run(self._async_abrasio.new_context(**kwargs))

    @property
    def browser(self) -> "Browser":
        """Get the underlying browser."""
        return self._async_abrasio.browser

    @property
    def is_cloud(self) -> bool:
        """Check if running in cloud mode."""
        return self._async_abrasio.is_cloud

    @property
    def is_local(self) -> bool:
        """Check if running in local mode."""
        return self._async_abrasio.is_local
