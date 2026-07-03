"""Client certificate (TLS Client Authentication) helpers.

Patchright/Playwright accept client certificates as a `client_certificates`
option on context creation (`new_context` / `launch_persistent_context`), each
entry shaped as `{origin, certPath|cert, keyPath|key, pfxPath|pfx, passphrase}`.
This module normalizes user-friendly snake_case input into that shape.

That native mechanism only works in **local mode** (it relies on a local SOCKS
proxy the browser must dial back into, which requires the browser and the
Playwright driver to be on the same machine). For **cloud mode** (remote
browser), use `route_with_client_certificate` below instead: it intercepts the
specific request via Playwright's `route()` API and replays it using Patchright's
own `APIRequestContext` — which handles TLS client certificates and proxy
configuration natively, keeping the request fully inside the Patchright session.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

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


def _pfx_to_pem_bytes(pfx_bytes: bytes, passphrase: Optional[str]) -> tuple:
    """
    Convert a PFX/PKCS12 bundle to (cert_pem, key_pem) bytes using Python's
    `cryptography` library, which bundles its own OpenSSL with legacy-provider
    support enabled. This handles ICP-Brasil certificates (RC2-40-CBC / 3DES
    PKCS12 encryption) that Node.js 18+/OpenSSL 3 would reject outright.
    """
    try:
        from cryptography.hazmat.primitives.serialization import (
            pkcs12, Encoding, PrivateFormat, NoEncryption,
        )
    except ImportError as e:
        raise AbrasioError(
            "Converting a PFX/PKCS12 certificate requires the 'cryptography' package. "
            "Install with: pip install abrasio[cert]"
        ) from e

    pfx_password = passphrase.encode() if passphrase else None
    private_key, cert_obj, _ = pkcs12.load_key_and_certificates(pfx_bytes, pfx_password)
    cert_pem = cert_obj.public_bytes(Encoding.PEM)
    key_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption())
    return cert_pem, key_pem


def _normalize_cert_for_patchright(certificate: Dict[str, Any]) -> Dict[str, Any]:
    """
    If the certificate is PFX/PKCS12, convert to PEM before passing to Playwright's
    APIRequestContext. Playwright's Node.js subprocess uses OpenSSL 3, which rejects
    legacy-encrypted PFX bundles (RC2-40-CBC / 3DES — common in ICP-Brasil certs)
    with 'Unsupported TLS certificate'. Python's cryptography library handles these
    legacy formats and produces a plain PEM cert+key that Node.js accepts.
    """
    pfx = certificate.get("pfx")
    pfx_path = certificate.get("pfxPath")
    if not pfx and not pfx_path:
        return certificate  # Already PEM — pass through unchanged.

    pfx_bytes = pfx if pfx else Path(pfx_path).read_bytes()
    cert_pem, key_pem = _pfx_to_pem_bytes(pfx_bytes, certificate.get("passphrase"))
    return {
        "origin": certificate["origin"],
        "cert": cert_pem,
        "key": key_pem,
        # key is already unencrypted after conversion — no passphrase needed.
    }


def _patchright_proxy(proxy: Optional[Union[str, Dict[str, str]]]) -> Optional[Dict[str, str]]:
    """Convert proxy config (string or dict) to Playwright's proxy dict format.

    Accepts:
      - dict:   {"server": "...", "username": "...", "password": "..."} (Playwright format)
      - string: "host:port" or "http://host:port" or "http://user:pass@host:port"
    """
    if not proxy:
        return None
    if isinstance(proxy, dict):
        result = dict(proxy)
        server = result.get("server", "")
        if server and "://" not in server:
            result["server"] = "http://" + server
        return result
    # String — may carry embedded credentials: http://user:pass@host:port
    from urllib.parse import urlparse as _up
    if "://" not in proxy:
        proxy = "http://" + proxy
    parsed = _up(proxy)
    port_part = f":{parsed.port}" if parsed.port else ""
    result: Dict[str, str] = {"server": f"{parsed.scheme}://{parsed.hostname}{port_part}"}
    if parsed.username:
        result["username"] = parsed.username
    if parsed.password:
        result["password"] = parsed.password
    return result


async def route_with_client_certificate(
    target: Any,
    url: Union[str, Any],
    certificate: Dict[str, Any],
    *,
    playwright_instance: Optional[Any] = None,
    relay_fn: Optional[Any] = None,
    proxy: Optional[Union[str, Dict[str, str]]] = None,
    timeout: float = 30.0,
    retries: int = 2,
    retry_backoff: float = 1.0,
) -> None:
    """
    Intercept `url` on `target` (Page or BrowserContext) and replay it with the
    given client certificate.

    Two execution modes — exactly one must be provided:

    **Local mode** (`playwright_instance`):
        Uses Patchright's own `APIRequestContext` to execute the mTLS request in the
        driver process. Pass `proxy` to route through a specific exit IP (e.g. a BR
        proxy when the driver runs outside Brazil).

    **Cloud/relay mode** (`relay_fn`):
        Calls an async function `relay_fn(cert_pem, key_pem, origin, method, url,
        headers, body, timeout) -> (status, headers, body)` that executes the request
        server-side (e.g. via the Abrasio API relay endpoint). The caller never needs
        to configure a proxy — the relay runs from within the session's region.

    Args:
        target: `Page` or `BrowserContext` to intercept requests on.
        url: URL/glob pattern to intercept, as accepted by Playwright's `route()`.
        certificate: A dict built with `build_client_certificate(...)`.
        playwright_instance: Active Playwright instance for local-mode execution.
        relay_fn: Async callable for cloud/relay-mode execution.
        proxy: Proxy for local-mode replay (ignored in relay mode).
        timeout: Request timeout in seconds. Defaults to 30s.
        retries: Extra attempts on transient failures. Default 2 (3 total).
        retry_backoff: Seconds × attempt number before each retry. Default 1.0.
    """
    if playwright_instance is None and relay_fn is None:
        raise AbrasioError(
            "route_with_client_certificate requires either 'playwright_instance' "
            "(local mode) or 'relay_fn' (cloud/relay mode)."
        )

    # Convert PFX → PEM if needed (handles legacy ICP-Brasil PKCS12 encryption
    # that Node.js/OpenSSL 3 rejects with "Unsupported TLS certificate").
    _cert = _normalize_cert_for_patchright(certificate)

    # Playwright only presents the client cert when the request's origin matches
    # the certificate's `origin` field exactly. Auto-correct from the route URL
    # to avoid ECONNRESET when the cert origin differs from the POST destination.
    if isinstance(url, str) and url.startswith("http"):
        from urllib.parse import urlparse as _urlparse
        _parsed = _urlparse(url)
        _origin = f"{_parsed.scheme}://{_parsed.netloc}"
        if _origin and _cert.get("origin") != _origin:
            logger.debug(
                f"Certificate origin overridden: {_cert.get('origin')!r} → {_origin!r} "
                f"(derived from route URL)"
            )
            _cert = {**_cert, "origin": _origin}

    # Local mode: create an APIRequestContext with the client cert.
    request_context = None
    if playwright_instance is not None:
        request_context = await playwright_instance.request.new_context(
            client_certificates=[_cert],
            proxy=_patchright_proxy(proxy),
            ignore_https_errors=False,
        )

    async def _handler(route: Any) -> None:
        request = route.request
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ("content-length", "host")
        }
        body = request.post_data_buffer

        last_exc: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                if relay_fn is not None:
                    # Cloud/relay mode: delegate to the Abrasio API (runs in Brazil).
                    cert_pem = _cert.get("cert") or b""
                    key_pem = _cert.get("key") or b""
                    origin = _cert.get("origin", "")
                    status, resp_headers, resp_body = await relay_fn(
                        cert_pem, key_pem, origin,
                        request.method, request.url, headers, body, timeout,
                    )
                    await route.fulfill(status=status, headers=resp_headers, body=resp_body)
                else:
                    # Local mode: replay via local APIRequestContext.
                    response = await request_context.fetch(
                        request.url,
                        method=request.method,
                        headers=headers,
                        data=body,
                        timeout=timeout * 1000,
                        fail_on_status_code=False,
                        max_redirects=0,
                    )
                    await route.fulfill(response=response)
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
