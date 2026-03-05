"""
Human-like behavior simulation utilities.

Implements realistic human behavior patterns inspired by Camoufox:
- Bezier curve mouse movements with distance-aware timing
- Variable typing speed with occasional mistakes
- Natural scrolling with momentum
- Random micro-adjustments (jitter)

References:
- https://camoufox.com/fingerprint/cursor-movement/
- https://github.com/Xetera/ghost-cursor
- https://ijirt.org/publishedpaper/IJIRT183343_PAPER.pdf
"""

import asyncio
import random
import math
from typing import Optional, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from patchright.async_api import Page


# Fitts's Law constants for movement time calculation
FITTS_A = 0.1  # Reaction time
FITTS_B = 0.1  # Movement coefficient


def _bezier_point(t: float, points: List[Tuple[float, float]]) -> Tuple[float, float]:
    """
    Calculate point on a Bezier curve at parameter t.

    Uses De Casteljau's algorithm for arbitrary degree curves.
    """
    n = len(points)
    if n == 1:
        return points[0]

    new_points = []
    for i in range(n - 1):
        x = (1 - t) * points[i][0] + t * points[i + 1][0]
        y = (1 - t) * points[i][1] + t * points[i + 1][1]
        new_points.append((x, y))

    return _bezier_point(t, new_points)


def _generate_control_points(
    start: Tuple[float, float],
    end: Tuple[float, float],
    num_control: int = 2,
) -> List[Tuple[float, float]]:
    """
    Generate control points for a natural-looking Bezier curve.

    Creates slight deviations from straight line to mimic human movement.
    """
    points = [start]

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    distance = math.sqrt(dx * dx + dy * dy)

    # More deviation for longer distances
    deviation = min(distance * 0.3, 100)

    for i in range(num_control):
        # Position along the line (spread control points)
        t = (i + 1) / (num_control + 1)

        # Base position on line
        base_x = start[0] + dx * t
        base_y = start[1] + dy * t

        # Add perpendicular deviation
        # Perpendicular vector: (-dy, dx) normalized
        if distance > 0:
            perp_x = -dy / distance
            perp_y = dx / distance
        else:
            perp_x, perp_y = 0, 0

        # Random deviation (can go either side)
        offset = random.gauss(0, deviation * 0.5)

        control_x = base_x + perp_x * offset
        control_y = base_y + perp_y * offset

        points.append((control_x, control_y))

    points.append(end)
    return points


def _calculate_movement_time(
    distance: float,
    min_time: float = 0.1,
    max_time: float = 1.5,
) -> float:
    """
    Calculate movement time based on distance using Fitts's Law.

    Longer distances take more time, but with diminishing returns.
    Includes randomness to avoid detection.
    """
    if distance < 1:
        return min_time

    # Fitts's Law: T = a + b * log2(1 + D/W)
    # Simplified: longer distance = more time
    base_time = FITTS_A + FITTS_B * math.log2(1 + distance / 10)

    # Add randomness (±20%)
    time = base_time * random.uniform(0.8, 1.2)

    return max(min_time, min(max_time, time))


def _add_jitter(point: Tuple[float, float], amount: float = 1.0) -> Tuple[float, float]:
    """Add small random jitter to a point (micro-adjustments)."""
    return (
        point[0] + random.gauss(0, amount),
        point[1] + random.gauss(0, amount),
    )


async def human_move_to(
    page: "Page",
    x: float,
    y: float,
    *,
    min_time: float = 0.1,
    max_time: float = 1.5,
    steps_per_second: int = 60,
    jitter: float = 0.5,
) -> None:
    """
    Move mouse to position using human-like Bezier curve trajectory.

    Based on Camoufox's cursor movement implementation with distance-aware
    timing and natural trajectories.

    Args:
        page: Patchright Page object
        x: Target X coordinate
        y: Target Y coordinate
        min_time: Minimum movement duration in seconds
        max_time: Maximum movement duration in seconds
        steps_per_second: Animation smoothness (higher = smoother)
        jitter: Amount of micro-adjustment noise
    """
    # Get current mouse position (approximate from viewport center if unknown)
    try:
        viewport = page.viewport_size
        if viewport:
            current_x = viewport["width"] / 2
            current_y = viewport["height"] / 2
        else:
            current_x, current_y = 500, 300
    except Exception:
        current_x, current_y = 500, 300

    start = (current_x, current_y)
    end = (x, y)

    # Calculate distance and movement time
    distance = math.sqrt((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2)
    duration = _calculate_movement_time(distance, min_time, max_time)

    # Generate Bezier curve control points
    control_points = _generate_control_points(start, end)

    # Calculate number of steps
    num_steps = max(int(duration * steps_per_second), 10)

    # Generate path points with easing (slow start, fast middle, slow end)
    for i in range(num_steps + 1):
        # Ease-in-out timing function
        t = i / num_steps
        # Cubic ease-in-out
        if t < 0.5:
            eased_t = 4 * t * t * t
        else:
            eased_t = 1 - pow(-2 * t + 2, 3) / 2

        # Get point on Bezier curve
        point = _bezier_point(eased_t, control_points)

        # Add jitter for micro-adjustments (less at start/end)
        jitter_amount = jitter * math.sin(t * math.pi)  # Peak in middle
        point = _add_jitter(point, jitter_amount)

        # Move mouse
        await page.mouse.move(point[0], point[1])

        # Wait for next frame
        await asyncio.sleep(duration / num_steps)


async def human_click(
    page: "Page",
    selector: Optional[str] = None,
    x: Optional[float] = None,
    y: Optional[float] = None,
    *,
    offset_range: int = 5,
    move_first: bool = True,
    double_click: bool = False,
) -> None:
    """
    Click with human-like mouse movement and slight position offset.

    Args:
        page: Patchright Page object
        selector: Element selector (optional if x, y provided)
        x: Target X coordinate (optional if selector provided)
        y: Target Y coordinate (optional if selector provided)
        offset_range: Maximum offset in pixels from center
        move_first: Whether to move mouse naturally before clicking
        double_click: Whether to double-click
    """
    # Determine target coordinates
    if selector:
        element = await page.query_selector(selector)
        if not element:
            raise ValueError(f"Element not found: {selector}")

        box = await element.bounding_box()
        if not box:
            # Fallback to direct click
            if double_click:
                await element.dblclick()
            else:
                await element.click(delay=3000, steps=7)
            return

        # Random position within element (not just center)
        x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
        y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
    elif x is None or y is None:
        raise ValueError("Either selector or x,y coordinates must be provided")

    # Add small random offset
    x += random.randint(-offset_range, offset_range)
    y += random.randint(-offset_range, offset_range)

    # Move to position naturally
    if move_first:
        await human_move_to(page, x, y)

    # Small pause before clicking (human reaction time)
    await asyncio.sleep(random.uniform(0.05, 0.15))

    # Click
    if double_click:
        await page.mouse.dblclick(x, y)
    else:
        await page.mouse.click(x, y, delay=3000)


# Typing speed varies by character (common letters are typed faster)
COMMON_CHARS = set("etaoinshrdlu ")
UNCOMMON_CHARS = set("zxqjkvbp")


async def human_type(
    page: "Page",
    text: str,
    selector: Optional[str] = None,
    *,
    min_delay_ms: int = 30,
    max_delay_ms: int = 150,
    mistake_probability: float = 0.02,
    think_pause_probability: float = 0.05,
) -> None:
    """
    Type text with human-like timing, including occasional mistakes.

    Features:
    - Variable typing speed (faster for common letters)
    - Occasional typos with corrections
    - Random pauses (thinking)
    - Burst typing (faster sequences)

    Args:
        page: Patchright Page object
        text: Text to type
        selector: Optional element selector to click first
        min_delay_ms: Minimum delay between keystrokes
        max_delay_ms: Maximum delay between keystrokes
        mistake_probability: Chance of making a typo (0-1)
        think_pause_probability: Chance of pausing to "think" (0-1)
    """
    if selector:
        await human_click(page, selector)
        await asyncio.sleep(random.uniform(0.1, 0.3))

    # Track burst typing (sequences typed faster)
    burst_mode = False
    burst_counter = 0

    for i, char in enumerate(text):
        # Determine base delay
        if char.lower() in COMMON_CHARS:
            base_delay = random.randint(min_delay_ms, int(max_delay_ms * 0.6))
        elif char.lower() in UNCOMMON_CHARS:
            base_delay = random.randint(int(min_delay_ms * 1.5), max_delay_ms)
        else:
            base_delay = random.randint(min_delay_ms, max_delay_ms)

        # Burst mode (faster typing for short sequences)
        if burst_mode:
            base_delay = int(base_delay * 0.5)
            burst_counter -= 1
            if burst_counter <= 0:
                burst_mode = False
        elif random.random() < 0.1:  # 10% chance to start burst
            burst_mode = True
            burst_counter = random.randint(3, 8)

        # Occasional thinking pause
        if random.random() < think_pause_probability:
            await asyncio.sleep(random.uniform(0.3, 1.0))

        # Occasional typo
        if random.random() < mistake_probability and char.isalpha():
            # Type wrong character
            wrong_char = _get_adjacent_key(char)
            await page.keyboard.type(wrong_char, delay=base_delay)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            # Delete it
            await page.keyboard.press("Backspace")
            await asyncio.sleep(random.uniform(0.05, 0.15))
            # Type correct character
            await page.keyboard.type(char, delay=base_delay)
        else:
            await page.keyboard.type(char, delay=base_delay)


def _get_adjacent_key(char: str) -> str:
    """Get a key adjacent to the given character (for typos)."""
    keyboard_layout = {
        "q": "wa", "w": "qeas", "e": "wsdr", "r": "edft", "t": "rfgy",
        "y": "tghu", "u": "yhji", "i": "ujko", "o": "iklp", "p": "ol",
        "a": "qwsz", "s": "awedxz", "d": "serfcx", "f": "drtgvc",
        "g": "ftyhbv", "h": "gyujnb", "j": "huikmn", "k": "jiolm",
        "l": "kop", "z": "asx", "x": "zsdc", "c": "xdfv", "v": "cfgb",
        "b": "vghn", "n": "bhjm", "m": "njk",
    }
    lower = char.lower()
    if lower in keyboard_layout:
        adjacent = keyboard_layout[lower]
        wrong = random.choice(adjacent)
        return wrong.upper() if char.isupper() else wrong
    return char


async def human_scroll(
    page: "Page",
    direction: str = "down",
    amount: Optional[int] = None,
    *,
    smooth: bool = True,
    duration: float = 0.5,
) -> None:
    """
    Scroll with human-like momentum and variable speed.

    Args:
        page: Patchright Page object
        direction: "up" or "down"
        amount: Pixels to scroll (random 200-600 if not specified)
        smooth: Whether to use smooth scrolling animation
        duration: Duration of smooth scroll in seconds
    """
    if amount is None:
        amount = random.randint(200, 600)

    if direction == "up":
        amount = -amount

    if not smooth:
        await page.mouse.wheel(0, amount)
        await asyncio.sleep(random.uniform(0.1, 0.3))
        return

    # Smooth scrolling with momentum
    steps = max(int(duration * 30), 5)
    step_amount = amount / steps

    for i in range(steps):
        # Ease-out (fast start, slow end) for momentum feel
        t = i / steps
        eased = 1 - pow(1 - t, 3)
        current_step = step_amount * (1 - eased * 0.5)  # Slow down at end

        await page.mouse.wheel(0, current_step)
        await asyncio.sleep(duration / steps)

    # Small pause after scroll
    await asyncio.sleep(random.uniform(0.1, 0.3))


async def random_delay(
    min_ms: int = 100,
    max_ms: int = 500,
) -> None:
    """
    Wait for a random duration to simulate human behavior.

    Args:
        min_ms: Minimum delay in milliseconds
        max_ms: Maximum delay in milliseconds
    """
    delay = random.randint(min_ms, max_ms) / 1000
    await asyncio.sleep(delay)


async def human_wait(
    min_seconds: float = 0.5,
    max_seconds: float = 2.0,
) -> None:
    """
    Wait with human-like variability.

    Uses a slightly skewed distribution (more short waits than long).

    Args:
        min_seconds: Minimum wait time
        max_seconds: Maximum wait time
    """
    # Beta distribution skewed toward shorter waits
    wait = min_seconds + (max_seconds - min_seconds) * (random.betavariate(2, 5))
    await asyncio.sleep(wait)


async def simulate_reading(
    page: "Page",
    min_seconds: float = 2.0,
    max_seconds: float = 8.0,
) -> None:
    """
    Simulate a user reading a page (scrolling, pausing).

    Args:
        page: Patchright Page object
        min_seconds: Minimum reading time
        max_seconds: Maximum reading time
    """
    reading_time = random.uniform(min_seconds, max_seconds)
    elapsed = 0

    while elapsed < reading_time:
        # Random action: scroll or just wait
        if random.random() < 0.3:
            await human_scroll(page, "down", random.randint(100, 300))

        wait = random.uniform(0.5, 2.0)
        await asyncio.sleep(wait)
        elapsed += wait


__all__ = [
    "human_move_to",
    "human_click",
    "human_type",
    "human_scroll",
    "random_delay",
    "human_wait",
    "simulate_reading",
]
