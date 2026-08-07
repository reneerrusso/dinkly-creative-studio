from __future__ import annotations

import httpx
import pytest

from app.backend.models.social_intelligence import BudgetSettings, MonitoredHandleInput, RefreshRequest
from app.backend.services.actor_registry_service import ActorRegistry
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.social_intelligence_service import SocialIntelligenceService


def client_factory(handler):
    return lambda **kwargs: httpx.Client(transport=httpx.MockTransport(handler), **kwargs)


def test_default_actor_loading_and_blank_override(repository: RepositoryService) -> None:
    registry = ActorRegistry(repository)
    assert registry.get_default("instagram")["actor_id"] == "apify~instagram-scraper"
    assert registry.get_default("tiktok")["actor_id"] == "clockworks~tiktok-profile-scraper"
    assert registry.get_effective("instagram", "")["source"] == "recommended"


def test_valid_override_is_verified_and_invalid_override_is_rejected(repository: RepositoryService) -> None:
    def ok(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer safe-token"
        return httpx.Response(200, json={"data": {"name": "custom"}})

    registry = ActorRegistry(repository, client_factory(ok))
    assert registry.validate_override("instagram", "safe-token", "owner~custom")["ready"] is True

    registry = ActorRegistry(repository, client_factory(lambda request: httpx.Response(404)))
    with pytest.raises(RepositoryError, match="invalid or unavailable"):
        registry.validate_override("instagram", "safe-token", "owner~missing")


def test_health_is_independent_and_registry_persists_enabled_state(repository: RepositoryService) -> None:
    def mixed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404 if "tiktok" in str(request.url) else 200, json={"data": {}})

    registry = ActorRegistry(repository, client_factory(mixed))
    assert registry.verify("instagram", "safe-token")["status"] == "Ready"
    assert registry.verify("tiktok", "safe-token")["status"] == "Unavailable"
    registry.set_enabled(True, False)
    restored = ActorRegistry(repository)
    assert restored.get_default("instagram")["enabled"] is True
    assert restored.get_default("tiktok")["enabled"] is False


def test_missing_token_does_not_attempt_actor_verification(repository: RepositoryService) -> None:
    def should_not_run(**kwargs):
        raise AssertionError("network must not be called")

    result = ActorRegistry(repository, should_not_run).verify("instagram", "")
    assert result["status"] == "Not configured"


def test_actor_override_does_not_bypass_budget_controls(repository: RepositoryService, monkeypatch: pytest.MonkeyPatch) -> None:
    service = SocialIntelligenceService(repository)
    service.secrets.set_apify_token("safe-test-token")
    service.budget.update_settings(BudgetSettings(enable_paid_provider_calls=False))
    monkeypatch.setattr(service.actors, "validate_override", lambda *args: {"ready": True})
    service.update_actor_settings("owner~instagram", "", True, True)
    handle, _ = service.add_handle(MonitoredHandleInput(platform="instagram", username="publicaccount"))
    preflight = service.preflight(RefreshRequest(handle_ids=[handle["id"]]))
    assert preflight["can_run"] is False
    assert any("Paid provider calls are disabled" in item for item in preflight["hard_stops"])
