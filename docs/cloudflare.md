# Cloudflare Turnstile

Abrasio can solve Cloudflare Turnstile and interstitial ("Verify you are human") challenges in
both local and cloud mode. It does **not** break the captcha: Patchright is undetected, so the
widget is clicked the way a user would.

Approach adapted from [Scrapling](https://github.com/D4Vinci/Scrapling)'s `StealthyFetcher`
(BSD-3-Clause, Copyright (c) 2024 Karim Shoair).

## Supported challenges

| Type | Behavior |
|------|----------|
| `non-interactive` | JS wait page. Waits up to 10s for it to clear itself. |
| `managed` / `interactive` | Full-page challenge. Waits for the widget iframe and clicks the checkbox. |
| `embedded` | Turnstile widget inside a normal page (e.g. a login form). Clicks the checkbox in the iframe. |

Not covered: reCAPTCHA, hCaptcha, GeeTest, image captchas, DataDome, Akamai. These need a
third-party solver service.

## Automatic mode

```python
async with Abrasio(solve_cloudflare=True) as browser:
    page = await browser.new_page()
    await page.goto("https://site-behind-cloudflare.com")  # solved before goto() returns
```

`solve_cloudflare=True` wraps `page.goto()` on every page of the session (existing and future).
If the challenge is still present after 3 attempts, an error is logged and the page is returned
as-is — `goto()` does not raise.

## Manual mode

Use it when the challenge appears after an interaction (e.g. clicking "Login"):

```python
from abrasio import Abrasio, solve_cloudflare

async with Abrasio(headless=False) as browser:
    page = await browser.new_page()
    await page.goto("https://example.com")
    ok = await solve_cloudflare(page, max_attempts=3)  # True = page is clear
```

| Argument | Default | Description |
|----------|---------|-------------|
| `page` | — | Patchright `Page` (local or cloud) |
| `max_attempts` | `3` | Click attempts before giving up |

Returns `True` if the page is clear (or never had a challenge), `False` otherwise.

## Tips

- Use `headless=False` for hard targets; headed Chrome passes more often.
- Turnstile depends heavily on IP reputation and fingerprint. Use a residential proxy or
  cloud mode if it keeps failing.
- Example: [`examples/cloudflare_solve.py`](../examples/cloudflare_solve.py).
