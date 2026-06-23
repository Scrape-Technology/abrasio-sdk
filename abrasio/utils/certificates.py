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
the browser using `httpx`, which supports client certificates natively.
"""

import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import httpx

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


async def route_with_client_certificate(
    target: Any,
    url: Union[str, Any],
    certificate: Dict[str, Any],
    *,
    proxy: Optional[Union[str, Dict[str, str]]] = None,
) -> None:
    """
    Intercept `url` on `target` (a Patchright `Page` or `BrowserContext`) and replay it
    outside the browser using the given client certificate, via `httpx`.

    This works in both local and cloud mode, unlike Playwright's native
    `client_certificates` option (local mode only) — the route handler always executes in
    the driver process, regardless of where the browser itself runs.

    Args:
        target: `Page` or `BrowserContext` to intercept requests on.
        url: URL/glob pattern to intercept, as accepted by Playwright's `route()`.
        certificate: A dict shaped like `build_client_certificate()`'s output.
        proxy: Proxy to replay the request through (string or `{"server","username","password"}`).
            Should match the browser session's proxy to keep a consistent exit IP.
    """
    cert_path, key_path, passphrase = materialize_certificate(certificate)
    httpx_proxy = _normalize_proxy(proxy)

    client = httpx.AsyncClient(
        cert=(cert_path, key_path, passphrase) if passphrase else (cert_path, key_path),
        proxy=httpx_proxy,
        verify=True,
    )

    async def _handler(route: Any) -> None:
        request = route.request
        try:
            headers = {
                k: v for k, v in request.headers.items()
                if k.lower() not in ("content-length", "host")
            }
            resp = await client.request(
                method=request.method,
                url=request.url,
                headers=headers,
                content=request.post_data_buffer,
                follow_redirects=False,
            )
            await route.fulfill(
                status=resp.status_code,
                headers=dict(resp.headers),
                body=resp.content,
            )
        except Exception:
            logger.exception(f"Certificate route replay failed for {request.url}")
            await route.abort()

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
