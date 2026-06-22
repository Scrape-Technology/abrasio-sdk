"""Client certificate (TLS Client Authentication) helpers.

Patchright/Playwright accept client certificates as a `client_certificates`
option on context creation (`new_context` / `launch_persistent_context`), each
entry shaped as `{origin, certPath|cert, keyPath|key, pfxPath|pfx, passphrase}`.
This module normalizes user-friendly snake_case input into that shape.
"""

from pathlib import Path
from typing import Any, Dict, Optional, Union

from .._exceptions import AbrasioError


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
