"""Client certificate (TLS Client Authentication) helpers.

Patchright/Playwright accept client certificates as a `client_certificates`
option on context creation (`new_context` / `launch_persistent_context`), each
entry shaped as `{origin, certPath|cert, keyPath|key, pfxPath|pfx, passphrase}`.
This module normalizes user-friendly snake_case input into that shape.

That native mechanism only works in **local mode** (it relies on a local SOCKS
proxy the browser must dial back into, which requires the browser and the
Playwright driver to be on the same machine). For **cloud mode** (remote
browser), use `route_with_client_certificate` below instead: it intercepts the
specific request via Playwright's `route()` API — which always executes in the
driver process, regardless of where the browser runs — and replays it outside
the browser using `curl_cffi`, which supports client certificates natively and
can impersonate a real browser's TLS/HTTP fingerprint (requires the `tls` extra:
`pip install abrasio[tls]`).
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from .._exceptions import AbrasioError

logger = logging.getLogger("abrasio.certificates")


def build_client_certificate(
    origin: str,
    *,
    cert: Optional[bytes] = None,
    cert_path: Optional[Union[str, Path]] = None,
    key: Optional[bytes] = None,
    key_path: Optional[Union[str, Path]] = None,
    pfx: Optional[bytes] = None,
    pfx_path: Optional[Union[str, Path]] = None,
    passphrase: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a Patchright-compatible client certificate entry for TLS Client Auth.

    Used to authenticate with sites that require a client certificate during
    login (e.g. ICP-Brasil certificates on gov.br). Pass the result (wrapped
    in a list) as `client_certificates` to `Abrasio(...)` / `AbrasioConfig`.

    Args:
        origin: Exact origin the certificate applies to, e.g. "https://sso.acesso.gov.br".
        cert: PEM certificate bytes. Use with `key`.
        cert_path: Path to a PEM certificate file. Use with `key_path`.
        key: PEM private key bytes. Use with `cert`.
        key_path: Path to a PEM private key file. Use with `cert_path`.
        pfx: PFX/PKCS12 bundle bytes (certificate + key in one file).
        pfx_path: Path to a PFX/PKCS12 file.
        passphrase: Passphrase for the private key (PEM or PFX), if encrypted.

    Returns:
        Dict shaped for Patchright's `client_certificates` option.

    Raises:
        AbrasioError: If origin is missing, or neither a PEM pair nor a PFX is provided.
    """
    if not origin:
        raise AbrasioError("build_client_certificate requires 'origin' (e.g. 'https://example.com').")

    has_pem = bool(cert or cert_path) and bool(key or key_path)
    has_pfx = bool(pfx or pfx_path)

    if not has_pem and not has_pfx:
        raise AbrasioError(
            "build_client_certificate requires either both cert/cert_path and key/key_path (PEM), "
            "or pfx/pfx_path (PFX/PKCS12)."
        )

    entry: Dict[str, Any] = {"origin": origin}

    if cert is not None:
        entry["cert"] = cert
    if cert_path is not None:
        entry["certPath"] = str(cert_path)
    if key is not None:
        entry["key"] = key
    if key_path is not None:
        entry["keyPath"] = str(key_path)
    if pfx is not None:
        entry["pfx"] = pfx
    if pfx_path is not None:
        entry["pfxPath"] = str(pfx_path)
    if passphrase is not None:
        entry["passphrase"] = passphrase

    return entry


def _write_temp(suffix: str, data: bytes) -> str:
    """Write bytes to a private temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="abrasio_cert_")
    try:
        with open(fd, "wb") as f:
            f.write(data)
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise
    return path


def materialize_certificate(certificate: Dict[str, Any]) -> Tuple[str, str, Optional[str]]:
    """
    Normalize a `build_client_certificate()` entry into `(cert_path, key_path, passphrase)`
    ready to pass as `httpx`'s `cert=` option.

    PFX/PKCS12 entries are converted to PEM (requires the `cryptography` package — install
    with `pip install abrasio[cert]`). `cert`/`key` bytes are written to private temp files;
    `certPath`/`keyPath` are passed through unchanged.

    Args:
        certificate: A dict shaped like `build_client_certificate()`'s output.

    Returns:
        (cert_path, key_path, passphrase) for `httpx.AsyncClient(cert=...)`.

    Raises:
        AbrasioError: If the entry has neither a PEM pair nor a PFX, or `cryptography`
            is missing when a PFX needs converting.
    """
    passphrase = certificate.get("passphrase")

    pfx_path = certificate.get("pfxPath")
    pfx = certificate.get("pfx")
    if pfx_path or pfx:
        try:
            from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption
        except ImportError as e:
            raise AbrasioError(
                "Converting a PFX/PKCS12 certificate requires the 'cryptography' package. "
                "Install with: pip install abrasio[cert]"
            ) from e

        pfx_bytes = pfx if pfx else Path(pfx_path).read_bytes()
        pfx_password = passphrase.encode() if passphrase else None
        private_key, cert_obj, _ = pkcs12.load_key_and_certificates(pfx_bytes, pfx_password)

        cert_pem = cert_obj.public_bytes(Encoding.PEM)
        key_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption())

        return _write_temp(".pem", cert_pem), _write_temp(".key", key_pem), None

    cert_path = certificate.get("certPath")
    cert_bytes = certificate.get("cert")
    key_path = certificate.get("keyPath")
    key_bytes = certificate.get("key")

    if not (cert_path or cert_bytes) or not (key_path or key_bytes):
        raise AbrasioError(
            "materialize_certificate requires either certPath/cert + keyPath/key (PEM), or "
            "pfxPath/pfx (PFX/PKCS12)."
        )

    resolved_cert_path = str(cert_path) if cert_path else _write_temp(".pem", cert_bytes)
    resolved_key_path = str(key_path) if key_path else _write_temp(".key", key_bytes)

    return resolved_cert_path, resolved_key_path, passphrase


def _decrypt_pem_key(key_path: str, passphrase: str) -> str:
    """
    Re-write an encrypted PEM private key as an unencrypted one and return its path.

    curl_cffi's `cert` option only accepts a plain (cert, key) file pair — no passphrase —
    so an encrypted PEM key needs to be decrypted up front, same as PFX keys already are
    in `materialize_certificate()`.
    """
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key, Encoding, PrivateFormat, NoEncryption
    except ImportError as e:
        raise AbrasioError(
            "Using a passphrase-protected PEM key requires the 'cryptography' package. "
            "Install with: pip install abrasio[cert]"
        ) from e

    private_key = load_pem_private_key(Path(key_path).read_bytes(), password=passphrase.encode())
    key_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption())
    return _write_temp(".key", key_pem)


async def route_with_client_certificate(
    target: Any,
    url: Union[str, Any],
    certificate: Dict[str, Any],
    *,
    proxy: Optional[Union[str, Dict[str, str]]] = None,
    timeout: float = 30.0,
    retries: int = 2,
    retry_backoff: float = 1.0,
    impersonate: str = "chrome",
) -> None:
    """
    Intercept `url` on `target` (a Patchright `Page` or `BrowserContext`) and replay it
    outside the browser using the given client certificate, via `curl_cffi`. Requires the
    `tls` extra: `pip install abrasio[tls]`.

    This works in both local and cloud mode, unlike Playwright's native
    `client_certificates` option (local mode only) — the route handler always executes in
    the driver process, regardless of where the browser itself runs.

    Uses `curl_cffi` (not `httpx`) so the replayed request's TLS/HTTP fingerprint matches
    a real Chrome (`impersonate`), instead of Python's default OpenSSL fingerprint — sites
    with anti-fraud/WAF checks in front of sensitive mTLS endpoints (e.g. ICP-Brasil logins
    on gov.br) can otherwise flag the mismatch between the browser's own fingerprint and a
    plain-Python client replaying one of its requests.

    Args:
        target: `Page` or `BrowserContext` to intercept requests on.
        url: URL/glob pattern to intercept, as accepted by Playwright's `route()`.
        certificate: A dict shaped like `build_client_certificate()`'s output.
        proxy: Proxy to replay the request through (string or `{"server","username","password"}`).
            Should match the browser session's proxy to keep a consistent exit IP.
        timeout: Request timeout in seconds. Defaults to 30s, since a timeout here aborts
            the route and leaves the page on a failed navigation (`chrome-error://chromewebdata/`).
        retries: Extra attempts after the first one if the replay raises (connection/timeout/
            proxy/SSL errors from a flaky proxy). Default 2 (3 attempts total). Does not retry
            on HTTP error responses (4xx/5xx) — only on request exceptions, since those are the
            ones that abort the route instead of returning a real response to the page.
        retry_backoff: Seconds to wait before each retry, multiplied by the attempt number
            (1st retry waits `retry_backoff`, 2nd waits `2 * retry_backoff`, ...). Default 1.0.
        impersonate: `curl_cffi` browser fingerprint to mimic. Default "chrome". Pass None
            to disable impersonation (plain curl TLS fingerprint).
    """
    try:
        from curl_cffi.requests import AsyncSession
    except ImportError as e:
        raise AbrasioError(
            "route_with_client_certificate requires the 'curl_cffi' package. "
            "Install with: pip install abrasio[tls]"
        ) from e

    cert_path, key_path, passphrase = materialize_certificate(certificate)
    if passphrase:
        key_path = _decrypt_pem_key(key_path, passphrase)
    cert = (cert_path, key_path)
    cffi_proxy = _normalize_proxy(proxy)

    client = AsyncSession()

    async def _handler(route: Any) -> None:
        request = route.request
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ("content-length", "host")
        }

        last_exc: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                resp = await client.request(
                    method=request.method,
                    url=request.url,
                    headers=headers,
                    data=request.post_data_buffer,
                    allow_redirects=False,
                    cert=cert,
                    proxy=cffi_proxy,
                    verify=True,
                    timeout=timeout,
                    impersonate=impersonate,
                )
                await route.fulfill(
                    status=resp.status_code,
                    headers=dict(resp.headers),
                    body=resp.content,
                )
                return
            except Exception as e:
                last_exc = e
                if attempt < retries:
                    wait = retry_backoff * (attempt + 1)
                    logger.warning(
                        f"Certificate route replay attempt {attempt + 1}/{retries + 1} "
                        f"failed for {request.url}: {e!r}. Retrying in {wait:.1f}s."
                    )
                    await asyncio.sleep(wait)

        logger.exception(
            f"Certificate route replay failed for {request.url} after "
            f"{retries + 1} attempt(s): {last_exc!r}",
            exc_info=last_exc,
        )
        # Fulfill with 502 instead of aborting — route.abort() causes the browser
        # to navigate to chrome-error://chromewebdata/, which is indistinguishable
        # from a real navigation and breaks URL-based error detection in callers.
        # A 502 response keeps the page on a normal HTTP error that callers can handle.
        error_body = (
            f"[abrasio] Certificate route replay failed after {retries + 1} "
            f"attempt(s): {last_exc!r}"
        ).encode()
        await route.fulfill(
            status=502,
            headers={"content-type": "text/plain; charset=utf-8"},
            body=error_body,
        )

    await target.route(url, _handler)


def _normalize_proxy(proxy: Optional[Union[str, Dict[str, str]]]) -> Optional[str]:
    """Normalize Abrasio's proxy config (str or dict) into an httpx proxy URL."""
    if not proxy:
        return None
    if isinstance(proxy, str):
        return proxy if "://" in proxy else f"http://{proxy}"

    server = proxy.get("server", "")
    if "://" not in server:
        server = f"http://{server}"
    username = proxy.get("username")
    password = proxy.get("password")
    if username and password:
        scheme, _, rest = server.partition("://")
        return f"{scheme}://{username}:{password}@{rest}"
    return server
