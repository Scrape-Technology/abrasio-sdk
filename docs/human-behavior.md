# Human Behavior Simulation

Modern anti-bot systems analyze user interaction patterns to detect automation. This guide explains how to use Abrasio's human behavior utilities to make automated input look like a real user's.

## Why Human Behavior Matters

Anti-bot systems look for:

| Pattern | Human | Bot |
|---------|-------|-----|
| Mouse movement | Curved, variable speed | Straight lines, constant speed |
| Typing speed | Variable, mistakes | Constant, perfect |
| Click position | Random within target | Exact center |
| Scrolling | Momentum, variable | Instant, fixed amounts |
| Timing | Random delays | Predictable patterns |

## Import All Utilities

```python
from abrasio.utils import (
    human_move_to,      # Bezier curve mouse movement
    human_click,        # Natural click with movement
    human_type,         # Variable-speed typing with mistakes
    human_scroll,       # Smooth scrolling with momentum
    human_wait,         # Random wait (skewed distribution)
    random_delay,       # Simple random delay
    simulate_reading,   # Simulate page reading behavior
)
```

## Mouse Movement

### human_move_to()

Moves the mouse using Bezier curves with natural timing.

```python
from abrasio.utils import human_move_to

# Move to coordinates with natural trajectory
await human_move_to(page, x=500, y=300)

# Customize timing
await human_move_to(
    page, x=500, y=300,
    min_time=0.2,         # Minimum movement duration
    max_time=2.0,         # Maximum movement duration
)
```

**How it works:**

1. **Bezier Curves**: Instead of straight lines, the mouse follows a curved path with 2-3 control points
2. **Distance-Aware Timing**: Uses Fitts's Law - longer distances take more time
3. **Ease-in-out**: Starts slow, speeds up, then slows down at the end
4. **Micro-jitter**: Small random movements simulate hand tremor

### human_click()

Clicks with natural mouse movement and position offset.

```python
from abrasio.utils import human_click

# Click an element by selector
await human_click(page, "button#submit")

# Customize behavior
await human_click(
    page,
    selector="button#submit",
    offset_range=10,      # Random offset from center (pixels)
    move_first=True,      # Move mouse naturally before clicking
)
```

**Features:**
- Clicks at random position within element (not just center)
- Moves mouse naturally before clicking
- Adds small random offset
- Includes brief pause before click (human reaction time)

## Typing

### human_type()

Types with variable speed and occasional mistakes.

```python
from abrasio.utils import human_type

# Basic typing
await human_type(page, "Hello, World!", selector="input#search")

# With customization
await human_type(
    page,
    "Hello, World!",
    selector="input#search",      # Optional: click element first
    min_delay_ms=30,              # Minimum delay between keys
    max_delay_ms=150,             # Maximum delay between keys
    mistake_probability=0.02,     # 2% chance of typo
    think_pause_probability=0.05, # 5% chance of thinking pause
)
```

**Features:**

| Feature | Description |
|---------|-------------|
| **Variable Speed** | Common letters (e, t, a, o) typed faster |
| **Burst Typing** | Random sequences typed rapidly |
| **Typos** | Occasional wrong key, then backspace and correct |
| **Pauses** | Random "thinking" pauses |

### Keyboard Layout for Typos

Typos simulate pressing adjacent keys:

```
Q W E R T Y U I O P
 A S D F G H J K L
  Z X C V B N M
```

Example: typing "hello" might produce "heklo" -> backspace -> "hello"

## Scrolling

### human_scroll()

Scrolls with momentum effect.

```python
from abrasio.utils import human_scroll

# Scroll down
await human_scroll(page, "down")

# Scroll up specific amount
await human_scroll(page, "up", amount=300)

# Smooth scrolling with momentum
await human_scroll(
    page,
    direction="down",
    amount=400,
    smooth=True,        # Enable smooth scrolling
    duration=0.5,       # Duration in seconds
)
```

**Momentum Effect:**
- Fast start, gradually slowing down
- Simulates finger flicking a touchscreen
- Variable speed throughout the scroll

### simulate_reading()

Simulates a user reading a page.

```python
from abrasio.utils import simulate_reading

# Simulate reading for 3-8 seconds
await simulate_reading(page, min_seconds=3, max_seconds=8)
```

**Behavior:**
- Random scrolling down
- Pauses between scrolls
- Variable reading time

## Delays and Waiting

### random_delay()

Simple random delay.

```python
from abrasio.utils import random_delay

# Wait 100-500ms
await random_delay(100, 500)

# Wait 1-3 seconds
await random_delay(1000, 3000)
```

### human_wait()

Wait with human-like distribution (more short waits).

```python
from abrasio.utils import human_wait

# Wait 0.5-2 seconds (skewed toward shorter waits)
await human_wait(0.5, 2.0)
```

Uses Beta distribution - most waits are shorter, occasional longer pauses.

## Complete Example

```python
import asyncio
from abrasio import Abrasio
from abrasio.utils import (
    human_click,
    human_type,
    human_scroll,
    human_wait,
    simulate_reading,
)

async def human_like_scraping():
    async with Abrasio(headless=False) as browser:
        page = await browser.new_page()

        # Navigate
        await page.goto("https://example.com")

        # Wait like a human would
        await human_wait(1, 2)

        # Click an element naturally
        await human_click(page, "a#some-link")

        # Wait for page load
        await page.wait_for_load_state("networkidle")

        # Simulate reading the page
        await simulate_reading(page, min_seconds=3, max_seconds=6)

        # Scroll down to see more
        await human_scroll(page, "down", 400, smooth=True)
        await human_wait(1, 2)

        # Type in a form
        await human_click(page, "input#search")
        await human_type(
            page,
            "search query",
            mistake_probability=0.02,
        )

        # Pause before submitting
        await human_wait(0.5, 1.5)
        await page.keyboard.press("Enter")

asyncio.run(human_like_scraping())
```

## Best Practices

### 1. Always Add Delays

```python
# Between actions
await human_wait(0.5, 1.5)

# Before important clicks
await human_wait(0.3, 0.8)
await human_click(page, "button")
```

### 2. Use Natural Movements

```python
# Move before clicking
await human_click(page, selector, move_first=True)
```

### 3. Vary Your Timing

```python
# Don't use fixed delays
await asyncio.sleep(1)          # Detectable pattern

# Use random delays
await human_wait(0.5, 2.0)     # Natural variation
```

### 4. Simulate Reading

```python
# After page load
await page.goto("https://example.com")
await simulate_reading(page, 2, 5)  # Read before acting
```

### 5. Make Mistakes Occasionally

```python
await human_type(
    page,
    text,
    mistake_probability=0.02,  # 2% typo rate is realistic
)
```

## Technical Details

### Bezier Curve Algorithm

The mouse movement uses cubic Bezier curves:

```
P(t) = (1-t)^3*P0 + 3(1-t)^2*t*P1 + 3(1-t)*t^2*P2 + t^3*P3
```

Where:
- P0 = Start point
- P1, P2 = Control points (random perpendicular deviation)
- P3 = End point
- t = Progress (0 to 1)

### Fitts's Law

Movement time is calculated using:

```
T = a + b * log2(1 + D/W)
```

Where:
- T = Movement time
- D = Distance to target
- W = Target width
- a, b = Constants

### Typing Speed Distribution

| Character Type | Speed Factor |
|---------------|--------------|
| Common (e, t, a, o, i, n, s, h, r, d, l, u, space) | 0.6x delay |
| Uncommon (z, x, q, j, k, v, b, p) | 1.5x delay |
| Other | 1.0x delay |
