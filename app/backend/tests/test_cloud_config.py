from __future__ import annotations

from pathlib import Path

import pytest

from app.backend.config import get_settings


def test_cloud_mode_rejects_localhost_urls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DINKLY_REPOSITORY_ROOT", str(tmp_path))
    monkeypatch.setenv("APP_MODE", "cloud")
    monkeypatch.setenv("DINKLY_FRONTEND_ORIGIN", "http://127.0.0.1:3000")
    monkeypatch.setenv("APP_URL", "http://127.0.0.1:3000")
    monkeypatch.setenv("API_URL", "http://127.0.0.1:8000")
    with pytest.raises(ValueError, match="public HTTPS"):
        get_settings()


def test_cloud_mode_centralizes_public_urls_and_origins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DINKLY_REPOSITORY_ROOT", str(tmp_path))
    monkeypatch.setenv("APP_MODE", "cloud")
    monkeypatch.setenv("DINKLY_FRONTEND_ORIGIN", "https://studio.example.com")
    monkeypatch.setenv("APP_URL", "https://studio.example.com")
    monkeypatch.setenv("API_URL", "https://api.example.com")
    monkeypatch.setenv("DINKLY_ALLOWED_ORIGINS", "https://preview.example.com")
    configured = get_settings()
    assert configured.api_url == "https://api.example.com"
    assert configured.public_base_url == "https://api.example.com"
    assert configured.allowed_origins == ("https://studio.example.com", "https://preview.example.com")
