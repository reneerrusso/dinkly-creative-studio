from __future__ import annotations

import os
import ssl
import sys
from pathlib import Path
from typing import Any

import certifi


class TlsConfigurationError(RuntimeError):
    """A local CA configuration prevents secure certificate validation."""


CA_OVERRIDE_VARIABLES = ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE")


def create_verified_ssl_context() -> ssl.SSLContext:
    """Build a hostname-checking, CERT_REQUIRED context using system trust or certifi."""
    override = _configured_ca_override()
    if override:
        context = ssl.create_default_context(cafile=str(override))
    elif _system_trust_is_available():
        context = ssl.create_default_context()
    else:
        context = ssl.create_default_context(cafile=certifi.where())

    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise TlsConfigurationError("Verified TLS context could not be created securely")
    return context


def verified_tls_diagnostics() -> dict[str, Any]:
    try:
        create_verified_ssl_context()
        verification_status = f"Ready — {_trust_source()} CA bundle"
    except (OSError, ssl.SSLError, TlsConfigurationError) as exc:
        verification_status = f"Configuration error — {exc}"
    return {
        "python_version": sys.version.split()[0],
        "openssl_version": ssl.OPENSSL_VERSION,
        "certifi_version": certifi.__version__,
        "certifi_path": certifi.where(),
        "tls_verification_status": verification_status,
    }


def _configured_ca_override() -> Path | None:
    for variable in CA_OVERRIDE_VARIABLES:
        value = os.environ.get(variable)
        if not value:
            continue
        path = Path(value).expanduser()
        if not path.is_file():
            raise TlsConfigurationError(f"{variable} points to a missing CA bundle")
        return path
    return None


def _system_trust_is_available() -> bool:
    paths = ssl.get_default_verify_paths()
    cafile = Path(paths.cafile) if paths.cafile else None
    capath = Path(paths.capath) if paths.capath else None
    return bool((cafile and cafile.is_file()) or (capath and capath.is_dir()))


def _trust_source() -> str:
    if any(os.environ.get(variable) for variable in CA_OVERRIDE_VARIABLES):
        return "configured"
    return "system" if _system_trust_is_available() else "certifi"
