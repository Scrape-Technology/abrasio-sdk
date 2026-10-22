"""Cloudflare Turnstile / interstitial solver for Patchright pages (local and cloud).

Approach adapted from Scrapling's StealthyFetcher (https://github.com/D4Vinci/Scrapling,
BSD-3-Clause, Copyright (c) 2024 Karim Shoair). It does not break the captcha: it relies on
Patchright being undetected, then clicks the Turnstile checkbox the way a user would.
Only Cloudflare Turnstile is covered (not reCAPTCHA / hCaptcha / image captchas).
"""

import logging
import re
from random import randint

from patchright.async_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger("abrasio.cloudflare")

_CF_FRAME = re.compile(r"^https?://challenges\.cloudflare\.com/cdn-cgi/challenge-platform/.*")
_INTERSTITIAL_TYPES = ("non-interactive", "managed", "interactive")
# Container of the widget on full-page (interstitial) challenges / embedded widgets.
_BOX_INTERSTITIAL = ".main-content p+div>div>div"
_BOX_EMBEDDED = "#cf_turnstile div, #cf-turnstile div, .turnstile>div>div"


def detect_cloudflare(html: str):
    """Return 'non-interactive' | 'managed' | 'interactive' | 'embedded' | None."""
    for ctype in _INTERSTITIAL_TYPES:
        if f"cType: '{ctype}'" in html:
            return ctype
    if "challenges.cloudflare.com/turnstile/v" in html:
        return "embedded"
    return None


async def _challenge(page: Page):
    return detect_cloudflare(await page.content())


async def _wait_cleared(page: Page, ctype: str, timeout_ms: int) -> bool:
    for _ in range(timeout_ms // 100):
        if await _challenge(page) is None:
            return True
        await page.wait_for_timeout(100)
    return await _challenge(page) is None


async def solve_cloudflare(page: Page, *, max_attempts: int = 3) -> bool:
    """Solve a Cloudflare challenge on the current page, if there is one.

    Call after `page.goto(...)`. Returns True when the page is clear (or never had a
    challenge), False if the challenge is still showing after `max_attempts`.
    """
    # Give the challenge a moment to render before concluding there is none.
    ctype = None
    for _ in range(50):
        ctype = await _challenge(page)
        if ctype and (ctype != "embedded" or page.frame(url=_CF_FRAME)):
            break
        ctype = None
        await page.wait_for_timeout(100)
    if not ctype:
        return True

    for attempt in range(max_attempts):
        logger.info("Cloudflare challenge '%s' (attempt %d/%d)", ctype, attempt + 1, max_attempts)

        if ctype == "non-interactive":
            # JS-only wait page: it clears itself.
            if await _wait_cleared(page, ctype, 10_000):
                return True
        else:
            frame = None
            for _ in range(20):
                frame = page.frame(url=_CF_FRAME)
                if frame or await _challenge(page) is None:
                    break
                await page.wait_for_timeout(500)

            if frame is None and await _challenge(page) is None:
                return True

            try:
                if ctype == "embedded" and frame is not None:
                    await frame.locator('input[type="checkbox"]').click(timeout=10_000, delay=randint(100, 200))
                    await page.wait_for_load_state("load")
                    return True

                box = await (await frame.frame_element()).bounding_box() if frame else None
                if not box:
                    sel = _BOX_EMBEDDED if ctype == "embedded" else _BOX_INTERSTITIAL
                    handles = await page.locator(sel).last.element_handles()
                    box = await handles[0].bounding_box() if handles else None
                if box:
                    # The checkbox sits ~27px right / ~26px down from the widget's corner.
                    await page.mouse.click(
                        box["x"] + randint(26, 28), box["y"] + randint(25, 27),
                        delay=randint(100, 200), button="left",
                    )
                    if await _wait_cleared(page, ctype, 10_000):
                        await page.wait_for_load_state("load")
                        return True
            except PlaywrightTimeoutError:
                pass

        await page.wait_for_timeout(1000)
        ctype = await _challenge(page)
        if ctype is None:
            return True

    logger.error("Cloudflare challenge not solved after %d attempts", max_attempts)
    return False


def _wrap_goto(page: Page) -> None:
    if getattr(page, "_abrasio_cf", False):
        return
    page._abrasio_cf = True
    goto = page.goto

    async def goto_and_solve(*args, **kwargs):
        response = await goto(*args, **kwargs)
        await solve_cloudflare(page)  # logs on failure; the page is returned as-is
        return response

    page.goto = goto_and_solve


async def solve_cloudflare_context(ctx) -> None:
    """Make page.goto() auto-solve Cloudflare on every page of `ctx` (existing and future)."""
    for page in list(ctx.pages):
        _wrap_goto(page)
    ctx.on("page", _wrap_goto)
