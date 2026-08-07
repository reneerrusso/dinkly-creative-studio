from __future__ import annotations

import json
import ssl
from pathlib import Path

import certifi
import pytest

from app.backend.services.agent_channels import SlackWebApiTransport
from app.backend.services.repository_service import RepositoryError
from app.backend.services.tls_service import TlsConfigurationError, create_verified_ssl_context


class Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_verified_context_requires_certificates_and_hostname_validation() -> None:
    context = create_verified_ssl_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert Path(certifi.where()).is_file()
    assert context.get_ca_certs()


def test_slack_auth_test_uses_verified_context(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def urlopen(_request, *, timeout, context):
        captured.update(timeout=timeout, context=context)
        return Response({"ok": True, "team": "DINKLY", "user": "DINKLY"})

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    result = SlackWebApiTransport("xoxb-test-token").call("auth.test", {})
    assert result["ok"] is True
    assert captured["context"].verify_mode == ssl.CERT_REQUIRED
    assert captured["context"].check_hostname is True


def test_slack_authentication_failure_is_not_reported_as_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: Response({"ok": False, "error": "invalid_auth"}),
    )
    with pytest.raises(RepositoryError, match="Slack API error: invalid_auth") as error:
        SlackWebApiTransport("xoxb-invalid").call("auth.test", {})
    assert "certificate" not in str(error.value).lower()


def test_bad_ca_override_has_a_clear_secure_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "missing.pem"))
    with pytest.raises(TlsConfigurationError, match="SSL_CERT_FILE points to a missing CA bundle"):
        create_verified_ssl_context()
    with pytest.raises(RepositoryError, match="Slack TLS configuration error"):
        SlackWebApiTransport("xoxb-test-token")


def test_slack_code_path_contains_no_tls_bypass() -> None:
    services = Path(__file__).resolve().parents[1] / "services"
    source = "\n".join(
        (services / filename).read_text(encoding="utf-8")
        for filename in ("agent_channels.py", "slack_service.py", "tls_service.py")
    )
    for forbidden in ("verify=False", "ssl=False", "CERT_NONE", "check_hostname = False"):
        assert forbidden not in source
