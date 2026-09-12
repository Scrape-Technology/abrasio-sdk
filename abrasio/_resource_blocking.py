"""Client-side resource-type blocking, shared by local and cloud browser modes."""

from typing import Iterable, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from patchright.async_api import BrowserContext

logger = logging.getLogger("abrasio.resource_blocking")

# Playwright/CDP resourceType() values. "document" and "xhr"/"fetch" are
# intentionally blockable too (caller's choice) — no built-in allowlist beyond
# validating the name isn't a typo.
_KNOWN_RESOURCE_TYPES = frozenset({
    "document", "stylesheet", "image", "media", "font", "script",
    "texttrack", "xhr", "fetch", "eventsource", "websocket", "manifest",
    "signedexchange", "ping", "cspviolationreport", "preflight", "other",
})


async def apply_resource_blocking(context: "BrowserContext", resource_types: Iterable[str]) -> None:
    """
    Abort every request whose Playwright resourceType is in `resource_types`.

    Runs inside the browser (CDP Fetch domain), before any network connection
    is made — so it reduces billed bytes_consumed in cloud mode, not just
    local bandwidth. No-op if `resource_types` is empty/None.
    """
    blocked = frozenset(resource_types or ())
    if not blocked:
        return

    unknown = blocked - _KNOWN_RESOURCE_TYPES
    if unknown:
        logger.warning(
            f"block_resources contains unrecognized resource type(s): {sorted(unknown)}. "
            f"Known types: {sorted(_KNOWN_RESOURCE_TYPES)}"
        )

    async def _handler(route):
        if route.request.resource_type in blocked:
            await route.abort()
        else:
            await route.continue_()

    await context.route("**/*", _handler)
