# abrasio-sdk/abrasio/human/actions.py
# -*- coding: utf-8 -*-
"""
Human-like browser interaction primitives for Abrasio SDK.

Mouse movement: WindMouse algorithm (same physics as HumanCursor/Camoufox).
  - Gravity pulls the cursor towards the target
  - Random "wind" adds realistic perturbations
  - Velocity management: accelerates in the middle, decelerates near target
  - Micro-tremors added within a few pixels of target
"""

from __future__ import annotations

import asyncio
import math
import random
import time
from typing import List, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# QWERTY adjacency map for realistic typo simulation
# ---------------------------------------------------------------------------
_QWERTY_ADJ: dict[str, str] = {
    'a': 'sqzw',  'b': 'vghn',  'c': 'xdfv',  'd': 'serfcx', 'e': 'wrsdf',
    'f': 'drtgvc', 'g': 'ftyh',  'h': 'gyujbn', 'i': 'uojk',   'j': 'huikmn',
    'k': 'jiolm',  'l': 'kop',   'm': 'njk',    'n': 'bhjm',   'o': 'iklp',
    'p': 'ol',     'q': 'wa',    'r': 'edft',   's': 'awedxz', 't': 'rfgy',
    'u': 'yhij',   'v': 'cfgb',  'w': 'qase',   'x': 'zsdc',   'y': 'tghu',
    'z': 'asx',
}

# ---------------------------------------------------------------------------
# Mouse position tracking
# ---------------------------------------------------------------------------

def _get_mouse_pos(page) -> Tuple[float, float]:
    x = getattr(page, "_abr_mouse_x", None)
    y = getattr(page, "_abr_mouse_y", None)
    if x is None or y is None:
        vp = page.viewport_size or {"width": 1366, "height": 768}
        x = vp["width"] * 0.5
        y = vp["height"] * 0.5
    return float(x), float(y)


def _set_mouse_pos(page, x: float, y: float) -> None:
    page._abr_mouse_x = x
    page._abr_mouse_y = y


# ---------------------------------------------------------------------------
# WindMouse path generation
# ---------------------------------------------------------------------------

def _wind_mouse_path(
    x0: float, y0: float,
    x1: float, y1: float,
    G_0: float = 9.0,
    W_0: float = 3.0,
    M_0: float = 15.0,
    D_0: float = 12.0,
    R: Optional[random.Random] = None,
) -> List[Tuple[float, float]]:
    """Generate a human-like mouse path from (x0,y0) to (x1,y1) using WindMouse."""
    if R is None:
        R = random.Random()

    pts: List[Tuple[float, float]] = []
    cx, cy = float(x0), float(y0)
    vx = vy = wx = wy = 0.0
    m0 = M_0

    for _ in range(3000):
        dist = math.hypot(x1 - cx, y1 - cy)
        if dist < 1.0:
            break

        w_mag = min(W_0, dist)

        if dist >= D_0:
            wx = wx / math.sqrt(3) + (2 * R.random() - 1) * w_mag / math.sqrt(5)
            wy = wy / math.sqrt(3) + (2 * R.random() - 1) * w_mag / math.sqrt(5)
        else:
            wx /= math.sqrt(3)
            wy /= math.sqrt(3)
            if m0 < 3:
                m0 = R.uniform(3, 5)
            else:
                m0 /= math.sqrt(5)

        vx += wx + G_0 * (x1 - cx) / dist
        vy += wy + G_0 * (y1 - cy) / dist

        v_mag = math.hypot(vx, vy)
        if v_mag > m0:
            rand_dist = m0 / 2.0 + R.uniform(0.0, m0 / 2.0)
            vx = (vx / v_mag) * rand_dist
            vy = (vy / v_mag) * rand_dist

        cx = max(0.0, cx + vx)
        cy = max(0.0, cy + vy)
        pts.append((cx, cy))

    pts.append((x1, y1))
    return pts


def _micro_tremor_points(
    x: float, y: float,
    n: int = 4,
    radius: float = 2.0,
    R: Optional[random.Random] = None,
) -> List[Tuple[float, float]]:
    if R is None:
        R = random.Random()
    pts = []
    for _ in range(n):
        angle = R.uniform(0, 2 * math.pi)
        r = R.uniform(0, radius)
        pts.append((x + r * math.cos(angle), y + r * math.sin(angle)))
    pts.append((x, y))
    return pts


# ---------------------------------------------------------------------------
# Core async primitives
# ---------------------------------------------------------------------------

async def human_mouse_move(
    page,
    to_xy: Tuple[float, float],
    *,
    speed_factor: float = 1.0,
    R: Optional[random.Random] = None,
) -> None:
    if R is None:
        R = random.Random()

    x0, y0 = _get_mouse_pos(page)
    x1, y1 = float(to_xy[0]), float(to_xy[1])

    dist = math.hypot(x1 - x0, y1 - y0)
    if dist < 5:
        await page.mouse.move(x1, y1)
        _set_mouse_pos(page, x1, y1)
        return

    m0 = max(8.0, min(30.0, dist / 20.0)) * speed_factor
    path = _wind_mouse_path(x0, y0, x1, y1, M_0=m0, R=R)
    step_delay_base = 0.003 / speed_factor

    for (mx, my) in path:
        await page.mouse.move(mx, my)
        await asyncio.sleep(R.uniform(step_delay_base * 0.5, step_delay_base * 2.5))

    # Overshoot (~20% chance)
    if dist > 30 and R.random() < 0.20:
        angle = math.atan2(y1 - y0, x1 - x0)
        overshoot = R.uniform(3.0, 9.0)
        ox = x1 + math.cos(angle) * overshoot
        oy = y1 + math.sin(angle) * overshoot
        await page.mouse.move(ox, oy)
        await asyncio.sleep(R.uniform(0.018, 0.045))
        await page.mouse.move(x1, y1)
        await asyncio.sleep(R.uniform(0.010, 0.025))

    _set_mouse_pos(page, x1, y1)


async def _resolve_box_async(page, target) -> Tuple[float, float]:
    if isinstance(target, str):
        el = await page.locator(target).element_handle()
    else:
        el = await target.element_handle() if hasattr(target, "element_handle") else target

    box = await el.bounding_box() if el else None
    if not box:
        vp = page.viewport_size or {"width": 1366, "height": 768}
        return vp["width"] / 2, vp["height"] / 2

    cx = box["x"] + box["width"] * random.uniform(0.25, 0.75)
    cy = box["y"] + box["height"] * random.uniform(0.35, 0.70)
    return cx, cy


async def click_human(
    page,
    selector_or_locator: Union[str, object],
    *,
    speed_factor: float = 1.0,
    seed: Optional[int] = None,
) -> None:
    R = random.Random(seed if seed is not None else (time.time_ns() & 0xFFFFFFFF))

    x1, y1 = await _resolve_box_async(page, selector_or_locator)
    await human_mouse_move(page, (x1, y1), speed_factor=speed_factor, R=R)

    for (tx, ty) in _micro_tremor_points(x1, y1, n=R.randint(2, 5), radius=1.5, R=R):
        await page.mouse.move(tx, ty)
        await asyncio.sleep(R.uniform(0.003, 0.010))

    await asyncio.sleep(R.uniform(0.04, 0.14))
    await page.mouse.down()
    await asyncio.sleep(R.uniform(0.025, 0.075))
    await page.mouse.up()
    await asyncio.sleep(R.uniform(0.04, 0.16))
    _set_mouse_pos(page, x1, y1)


async def type_human(
    page,
    text: str,
    *,
    char_delay_range: Tuple[float, float] = (0.035, 0.18),
    burst_chance: float = 0.25,
    typo_chance: float = 0.03,
    seed: Optional[int] = None,
) -> None:
    R = random.Random(seed if seed is not None else (time.time_ns() & 0xFFFFFFFF))
    buf: List[str] = []

    for ch in text:
        ch_lower = ch.lower()
        if typo_chance > 0 and R.random() < typo_chance and ch_lower in _QWERTY_ADJ:
            wrong = R.choice(_QWERTY_ADJ[ch_lower])
            await page.keyboard.type(wrong)
            await asyncio.sleep(R.uniform(0.08, 0.22))
            await page.keyboard.press("Backspace")
            await asyncio.sleep(R.uniform(0.05, 0.12))

        buf.append(ch)
        if R.random() < burst_chance and len(buf) < len(text) and len(buf) >= 2:
            await page.keyboard.type("".join(buf))
            buf.clear()
            await asyncio.sleep(R.uniform(0.10, 0.28))
            continue
        await page.keyboard.type(ch)
        delay = R.uniform(*char_delay_range)
        if R.random() < 0.08:
            delay += R.uniform(0.3, 0.9)
        await asyncio.sleep(delay)

    if buf:
        await page.keyboard.type("".join(buf))


def _ease_3phase(t: float) -> float:
    t = max(0.0, min(1.0, t))
    if t < 0.30:
        p = t / 0.30
        return p * p * 0.30
    elif t < 0.70:
        return 0.30 + (t - 0.30) * (0.40 / 0.40)
    else:
        p = (t - 0.70) / 0.30
        return 0.70 + (1.0 - (1.0 - p) ** 2) * 0.30


async def scroll_human(
    page,
    *,
    pixels: int = 800,
    duration_ms: float = 650.0,
    speed_factor: float = 1.0,
    ease: str = "3phase",
    seed: Optional[int] = None,
) -> None:
    R = random.Random(seed if seed is not None else (time.time_ns() & 0xFFFFFFFF))
    effective_ms = max(80.0, duration_ms / max(0.1, speed_factor))
    steps = max(10, int(effective_ms / 16))
    prev = 0
    for i in range(1, steps + 1):
        t = _ease_3phase(i / steps) if ease == "3phase" else (i / steps)
        curr = int(pixels * t)
        await page.mouse.wheel(0, curr - prev)
        prev = curr
        await asyncio.sleep(R.uniform(0.006, 0.020))


async def fill_human(
    page,
    selector_or_locator,
    text: str,
    *,
    char_delay_range: Tuple[float, float] = (0.040, 0.16),
    typo_chance: float = 0.03,
    seed: Optional[int] = None,
) -> None:
    R = random.Random(seed if seed is not None else (time.time_ns() & 0xFFFFFFFF))
    await click_human(page, selector_or_locator, seed=R.randint(0, 0xFFFFFFFF))
    await asyncio.sleep(R.uniform(0.08, 0.20))
    modifier = "Meta" if "mac" in (getattr(page, "_abr_platform", "") or "").lower() else "Control"
    await page.keyboard.press(f"{modifier}+a")
    await asyncio.sleep(R.uniform(0.05, 0.12))
    await type_human(
        page, text,
        char_delay_range=char_delay_range,
        typo_chance=typo_chance,
        seed=R.randint(0, 0xFFFFFFFF),
    )


# ---------------------------------------------------------------------------
# Visible cursor overlay (headed mode only)
# ---------------------------------------------------------------------------

_CURSOR_OVERLAY_JS = """
(function() {
  try {
    if (document.getElementById('__abr_cursor__')) return;
    var root = document.documentElement || document.body;
    if (!root) return;
    var el = document.createElement('div');
    el.id = '__abr_cursor__';
    el.style.cssText = [
      'position:fixed', 'top:0', 'left:0',
      'width:18px', 'height:18px',
      'background:rgba(255,80,0,0.80)',
      'border:2.5px solid rgba(255,255,255,0.95)',
      'border-radius:50%',
      'box-shadow:0 0 8px 3px rgba(255,100,0,0.55)',
      'pointer-events:none',
      'z-index:2147483647',
      'transform:translate(-50%,-50%)',
      'transition:left 0.018s linear,top 0.018s linear',
      'will-change:left,top',
    ].join(';');
    root.appendChild(el);
    document.addEventListener('mousemove', function(e) {
      el.style.left = e.clientX + 'px';
      el.style.top  = e.clientY + 'px';
    }, {passive: true});
  } catch(e) {}
})();
"""


async def humanize_page(
    page,
    *,
    headless: bool = False,
    speed_factor: float = 1.0,
) -> None:
    """
    Monkey-patches a Playwright async Page so every interaction is humanized.
    Idempotent — safe to call multiple times.
    """
    if getattr(page, "_abr_humanized", False):
        return
    page._abr_humanized = True

    # Note: cursor overlay is NOT injected here — it runs inside _hgoto after
    # navigation completes, which is the only safe moment (DOM is guaranteed ready).

    # ---- goto -------------------------------------------------------
    _orig_goto = page.goto

    async def _hgoto(url, **kwargs):
        R = random.Random()
        await asyncio.sleep(R.uniform(0.05, 0.30))
        result = await _orig_goto(url, **kwargs)
        await asyncio.sleep(R.uniform(0.10, 0.45))
        if not headless:
            try:
                await page.evaluate(_CURSOR_OVERLAY_JS)
            except Exception:
                pass
        return result

    page.goto = _hgoto

    # ---- click -------------------------------------------------------
    _orig_click = page.click

    async def _hclick(selector, *, button="left", **kwargs):
        if button == "left":
            try:
                await click_human(page, selector, speed_factor=speed_factor)
                return
            except Exception:
                pass
        return await _orig_click(selector, button=button, **kwargs)

    page.click = _hclick

    # ---- fill --------------------------------------------------------
    _orig_fill = page.fill

    async def _hfill(selector, value, **kwargs):
        try:
            await fill_human(page, selector, value)
            return
        except Exception:
            pass
        return await _orig_fill(selector, value, **kwargs)

    page.fill = _hfill

    # ---- type --------------------------------------------------------
    _orig_type = page.type

    async def _htype(selector, text, **kwargs):
        try:
            await click_human(page, selector, speed_factor=speed_factor)
            await type_human(page, text)
            return
        except Exception:
            pass
        return await _orig_type(selector, text, **kwargs)

    page.type = _htype

    # ---- hover -------------------------------------------------------
    _orig_hover = page.hover

    async def _hhover(selector, **kwargs):
        try:
            cx, cy = await _resolve_box_async(page, selector)
            await human_mouse_move(page, (cx, cy), speed_factor=speed_factor)
            return
        except Exception:
            pass
        return await _orig_hover(selector, **kwargs)

    page.hover = _hhover


async def humanize_context(
    ctx,
    *,
    headless: bool = False,
    speed_factor: float = 1.0,
) -> None:
    """
    Humanizes ALL pages in a Playwright BrowserContext (existing and future).

    - Patches page.goto / click / fill / type / hover on every page.
    - Listens for new pages and patches them automatically.
    - Cursor overlay is injected inside the patched goto, after navigation — never
      as add_init_script (which runs before DOM exists and causes navigation failures).
    """
    for page in list(ctx.pages):
        try:
            await humanize_page(page, headless=headless, speed_factor=speed_factor)
        except Exception:
            pass

    def _on_new_page(page):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(
                    humanize_page(page, headless=headless, speed_factor=speed_factor)
                )
        except Exception:
            pass

    ctx.on("page", _on_new_page)
