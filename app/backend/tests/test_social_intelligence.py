from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.backend.models.social_intelligence import (
    BudgetSettings,
    BulkHandleInput,
    ManualPostInput,
    MonitoredHandleInput,
    RefreshRequest,
)
from app.backend.providers.social_data import ApifyInstagramProvider, ProviderError, SocialDataProvider
from app.backend.services.agent_runtime_service import AgentRuntimeService
from app.backend.services.budget_service import BudgetService, BudgetStopped
from app.backend.services.circuit_breaker_service import CircuitBreakerService
from app.backend.services.repository_service import RepositoryService
from app.backend.services.secrets_service import SecretsService
from app.backend.services.social_intelligence_scheduler import SocialIntelligenceScheduler
from app.backend.services.social_intelligence_service import SocialIntelligenceService


class FakeProvider(SocialDataProvider):
    name = "apify"

    def __init__(self, platform: str, posts: list[dict] | None = None, error: ProviderError | None = None) -> None:
        self.platform = platform
        self.posts = posts or []
        self.error = error
        self.request_guard = None
        self.cancelled = False

    def validate_credentials(self) -> dict:
        return {"configured": True, "connected": True, "state": "Configured"}

    def validate_handle(self, handle: str) -> dict:
        return {"valid": True, "username": handle, "platform": self.platform}

    def estimate_run_cost(self, handles: int, posts_per_handle: int, usage_history: list[dict]) -> dict:
        return {
            "estimated_cost_low": 0.05 * handles,
            "estimated_cost_high": 0.1 * handles,
            "source": "test fixture estimate",
            "requires_confirmation": False,
        }

    def fetch_profile(self, handle: str) -> dict:
        return {}

    def fetch_recent_posts(self, handle: str, limit: int) -> list[dict]:
        if self.request_guard:
            self.request_guard("fake fetch")
        if self.error:
            raise self.error
        return [dict(item) for item in self.posts[:limit]]

    def fetch_post_details(self, post_id: str) -> dict:
        return {}

    def normalize_profile(self, raw: dict, handle: str) -> dict:
        return {}

    def normalize_post(self, raw: dict, handle: str) -> dict:
        return raw

    def get_usage(self) -> dict:
        return {"actual_cost": None, "usage_source": "estimated", "currency": "USD"}

    def get_provider_status(self) -> dict:
        return {"state": "Configured"}

    def cancel_active_request(self) -> bool:
        self.cancelled = True
        return True

    def health_check(self) -> dict:
        return self.validate_credentials()


def _enable_provider(repository: RepositoryService) -> SocialIntelligenceService:
    service = SocialIntelligenceService(repository)
    service.secrets.configure_apify("apify_test_token_1234", "instagram-actor", "tiktok-actor")
    service.budget.update_settings(BudgetSettings(enable_paid_provider_calls=True))
    return service


def _post(post_id: str, views: int | None = 100, caption: str = "Coffee together") -> dict[str, Any]:
    return {
        "platform": "instagram",
        "platform_post_id": post_id,
        "post_url": f"https://example.test/{post_id}",
        "caption": caption,
        "hashtags": ["coffee"],
        "posted_at": "2026-08-01T12:00:00+00:00",
        "media_type": "image",
        "remote_thumbnail_url": None,
        "duration_seconds": None,
        "view_count": views,
        "like_count": 10,
        "comment_count": 0,
        "share_count": None,
        "audio_name": None,
        "follower_count": 1000,
        "profile": {
            "username": "sample",
            "display_name": "Sample",
            "profile_url": "https://instagram.com/sample/",
            "followers": 1000,
            "following": None,
            "post_count": None,
            "verified": False,
        },
        "raw_metadata": {"provider_item_keys": ["id"]},
    }


def test_no_api_key_returns_structured_state(repository: RepositoryService) -> None:
    service = SocialIntelligenceService(repository)
    apify = service.providers()[0]
    assert apify["state"] == "Not configured"
    assert apify["configured"] is False
    assert service.providers()[1]["state"] == "Available"


def test_secure_key_save_masks_token_preserves_unrelated_values_and_removes_token(
    repository: RepositoryService,
) -> None:
    secrets = SecretsService(repository)
    secrets.path.write_text("UNRELATED_SETTING=keep-me\n", encoding="utf-8")
    token = "apify_private_token_abcd"
    status = secrets.configure_apify(token, "ig-actor", "tt-actor")

    assert status["configured"] is True
    assert status["masked_token"].endswith("abcd")
    assert token not in json.dumps(status)
    content = secrets.path.read_text(encoding="utf-8")
    assert "UNRELATED_SETTING=keep-me" in content
    assert "APIFY_API_TOKEN=" + token in content
    assert oct(secrets.path.stat().st_mode & 0o777) == "0o600"
    assert secrets.redact(f"Authorization: Bearer {token}") == "Authorization: [REDACTED] [REDACTED]"

    removed = secrets.remove_apify_token()
    assert removed["configured"] is False
    assert token not in secrets.path.read_text(encoding="utf-8")
    assert "UNRELATED_SETTING=keep-me" in secrets.path.read_text(encoding="utf-8")
    assert list(secrets.backup_directory.glob("*.bak"))


def test_apify_invalid_token_never_appears_in_result_or_url() -> None:
    token = "secret_invalid_token"

    def handler(request: httpx.Request) -> httpx.Response:
        assert token not in str(request.url)
        assert request.headers["Authorization"] == f"Bearer {token}"
        return httpx.Response(401, text="invalid token")

    provider = ApifyInstagramProvider(
        token,
        "actor",
        max_retries=0,
        client_factory=lambda **kwargs: httpx.Client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = provider.validate_credentials()
    assert result["connected"] is False
    assert result["error_code"] == "authentication"
    assert token not in json.dumps(result)


@pytest.mark.parametrize(
    ("status_code", "body", "expected"),
    [
        (402, "insufficient credit", "insufficient_credit"),
        (429, "rate limited", "rate_limited"),
        (404, "actor missing", "actor_unavailable"),
    ],
)
def test_apify_normalizes_provider_failures(status_code: int, body: str, expected: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text=body)

    provider = ApifyInstagramProvider(
        "safe-token-value",
        "actor",
        max_retries=0,
        client_factory=lambda **kwargs: httpx.Client(transport=httpx.MockTransport(handler), **kwargs),
    )
    with pytest.raises(ProviderError) as caught:
        provider.fetch_recent_posts("example", 2)
    assert caught.value.code == expected


def test_apify_timeout_is_bounded_and_truthful() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    provider = ApifyInstagramProvider(
        "safe-token-value",
        "actor",
        max_retries=0,
        client_factory=lambda **kwargs: httpx.Client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = provider.validate_credentials()
    assert result["error_code"] == "timeout"
    assert "timed out" in result["message"]


def test_apify_credit_message_wins_over_generic_forbidden_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="account suspended because of insufficient credit")

    provider = ApifyInstagramProvider(
        "safe-token-value",
        "actor",
        max_retries=0,
        client_factory=lambda **kwargs: httpx.Client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = provider.validate_credentials()
    assert result["error_code"] == "insufficient_credit"
    assert result["state"] == "Budget paused"


def test_budget_preflight_requires_confirmation_and_enforces_hard_limit(repository: RepositoryService) -> None:
    budget = BudgetService(repository)
    budget.update_settings(BudgetSettings(enable_paid_provider_calls=True))
    result = budget.preflight(
        handles=[{"enabled": True, "platform": "instagram"}],
        posts_per_handle=20,
        estimates=[{"estimated_cost_low": 0.4, "estimated_cost_high": 0.6, "requires_confirmation": False, "source": "fixture"}],
        provider_configured=True,
        provider_state="Closed",
    )
    assert result["can_run"] is True
    assert result["requires_confirmation"] is True
    assert result["estimated_cost_label"] == "Estimated provider cost"

    budget.record_usage(
        {
            "provider": "apify",
            "estimated_cost_before": 4.0,
            "actual_cost": None,
            "requests": 1,
            "items_returned": 1,
            "handles_processed": 1,
            "usage_source": "estimated",
            "status": "Completed",
        }
    )
    assert budget.usage_summary()["percent_used"] == 80
    with pytest.raises(BudgetStopped, match="80 percent"):
        budget.check_before_request(0.1, request_count=1, phase="retry")


def test_unknown_cost_and_scheduled_run_are_stopped_for_confirmation(repository: RepositoryService) -> None:
    budget = BudgetService(repository)
    budget.update_settings(BudgetSettings(enable_paid_provider_calls=True, schedule_enabled=True))
    result = budget.preflight(
        handles=[{"enabled": True, "platform": "instagram"}],
        posts_per_handle=10,
        estimates=[{"estimated_cost_low": None, "estimated_cost_high": None, "requires_confirmation": True, "source": "unknown"}],
        provider_configured=True,
        provider_state="Closed",
        scheduled=True,
    )
    assert result["requires_confirmation"] is True
    assert result["can_run"] is False
    assert any("Scheduled refresh skipped" in item for item in result["hard_stops"])


def test_daily_monthly_hard_stops_and_explicit_overage(repository: RepositoryService) -> None:
    budget = BudgetService(repository)
    budget.update_settings(
        BudgetSettings(
            enable_paid_provider_calls=True,
            daily_provider_budget=0.2,
            monthly_provider_budget=1.0,
            automatically_pause_at_80_percent=False,
        )
    )
    budget.record_usage({"estimated_cost_before": 0.2, "actual_cost": None})
    with pytest.raises(BudgetStopped, match="daily budget"):
        budget.check_before_request(0.01, request_count=1, phase="second platform")

    repository.write_json("data/provider_usage.json", [])
    budget.update_settings(
        BudgetSettings(
            enable_paid_provider_calls=True,
            daily_provider_budget=10,
            monthly_provider_budget=0.2,
            automatically_pause_at_80_percent=False,
        )
    )
    budget.record_usage({"estimated_cost_before": 0.2, "actual_cost": None})
    with pytest.raises(BudgetStopped, match="monthly budget"):
        budget.check_before_request(0.01, request_count=1, phase="retry")

    budget.update_settings(
        BudgetSettings(
            enable_paid_provider_calls=True,
            daily_provider_budget=0.1,
            monthly_provider_budget=0.1,
            allow_paid_overage=True,
        )
    )
    budget.check_before_request(5, request_count=1, phase="confirmed overage")
    budget.check_after_usage()


def test_post_call_usage_check_pauses_at_eighty_percent(repository: RepositoryService) -> None:
    budget = BudgetService(repository)
    budget.update_settings(BudgetSettings(enable_paid_provider_calls=True, monthly_provider_budget=5))
    budget.record_usage({"estimated_cost_before": 4, "actual_cost": None})
    with pytest.raises(BudgetStopped, match="80 percent"):
        budget.check_after_usage()


def test_handle_normalization_bulk_preview_and_duplicate_protection(repository: RepositoryService) -> None:
    service = SocialIntelligenceService(repository)
    preview = service.preview_bulk_handles(
        BulkHandleInput(text="instagram,@Account.One\ntiktok,https://www.tiktok.com/@Account_Two\ninstagram,@account.one")
    )
    assert [(item["platform"], item["username"]) for item in preview["handles"]] == [
        ("instagram", "account.one"),
        ("tiktok", "account_two"),
    ]
    created = service.add_bulk_handles(
        BulkHandleInput(text="instagram,@Account.One\ntiktok,https://www.tiktok.com/@Account_Two")
    )
    assert len(created) == 2
    with pytest.raises(Exception, match="already monitored"):
        service.add_handle(MonitoredHandleInput(platform="instagram", username="account.one"))


def test_manual_import_preserves_zero_missing_metrics_and_snapshot_history(repository: RepositoryService) -> None:
    service = SocialIntelligenceService(repository)
    handle, _ = service.add_handle(MonitoredHandleInput(platform="instagram", username="sample", provider="manual-import"))
    payload = ManualPostInput(
        handle_id=handle["id"],
        platform="instagram",
        platform_post_id="post-1",
        caption="Coffee together",
        view_count=0,
        like_count=0,
        comment_count=None,
        share_count=None,
    )
    first = service.add_manual_post(payload)
    second = service.add_manual_post(payload)

    assert first["created"] is True
    assert second["skipped"] is True
    assert len(service.list_posts()) == 1
    assert len(service.snapshots(first["post"]["id"])) == 2
    post = service.list_posts()[0]
    assert post["view_count"] == 0
    assert post["comment_count"] is None
    assert post["performance"]["engagement_rate_by_views"] is None
    assert post["velocity_message"] is None


def test_manual_csv_import_deduplicates_posts(repository: RepositoryService) -> None:
    service = SocialIntelligenceService(repository)
    content = (
        b"platform,username,post_id,caption,views,likes,comments,shares\n"
        b"instagram,sample,p1,Coffee together,100,20,2,\n"
        b"instagram,sample,p1,Coffee together,120,22,3,\n"
    )
    result = service.import_posts("posts.csv", content)
    assert result["fixture"] is False
    assert result["posts_created"] == 1
    assert result["posts_skipped"] == 1
    assert result["snapshots_created"] == 2
    assert service.list_posts()[0]["share_count"] is None


def test_baselines_learning_original_direction_and_prompt_handoff(repository: RepositoryService) -> None:
    service = SocialIntelligenceService(repository)
    handle, _ = service.add_handle(MonitoredHandleInput(platform="instagram", username="sample", provider="manual-import"))
    for post_id, views in (("p1", 100), ("p2", 100), ("p3", 1000)):
        service.add_manual_post(
            ManualPostInput(
                handle_id=handle["id"],
                platform="instagram",
                platform_post_id=post_id,
                caption="Coffee together at home",
                view_count=views,
                like_count=10,
                follower_count=1000,
            )
        )
    posts = service.list_posts()
    standout = next(item for item in posts if item["platform_post_id"] == "p3")
    assert standout["performance"]["account_median"] == 100
    assert standout["performance"]["multiplier"] == 10
    assert standout["performance"]["sample_size"] == 3

    analysis = service.analyze_existing_data()
    assert analysis == {"learnings_created": 1, "concept_directions_created": 1}
    learning = service.list_learnings()[0]
    assert learning["confidence"] == "Low"
    assert "does not establish causation" in learning["hypothesis"]
    direction = service.list_directions()[0]
    assert direction["title_pair"] == {"left": "COFFEE", "right": "COFFEE WITH YOU"}
    assert "Do not copy exact captions" in direction["must_not_copy"]
    assert "DINKLY" in direction["why_original"]

    handoff = service.open_direction_in_prompt_builder(direction["id"])
    assert handoff["href"].startswith("/prompt-builder?concept=")
    assert service.concepts.get(handoff["concept_id"])["source"] == "app"


def test_manual_classification_override_wins(repository: RepositoryService) -> None:
    service = SocialIntelligenceService(repository)
    handle, _ = service.add_handle(MonitoredHandleInput(platform="instagram", username="sample"))
    record = service.add_manual_post(
        ManualPostInput(handle_id=handle["id"], platform="instagram", platform_post_id="p1", caption="Coffee")
    )["post"]
    updated = service.override_classification(record["id"], {"theme": "manual-theme", "activity": "reading"})
    assert updated["creative_attributes"]["theme"] == "manual-theme"
    assert updated["creative_attributes"]["manual_override"] is True


def test_partial_provider_success_preserves_successful_platform_data(
    repository: RepositoryService, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _enable_provider(repository)
    instagram, _ = service.add_handle(MonitoredHandleInput(platform="instagram", username="good"))
    tiktok, _ = service.add_handle(MonitoredHandleInput(platform="tiktok", username="unavailable"))
    providers = {
        "instagram": FakeProvider("instagram", [_post("ig-1")]),
        "tiktok": FakeProvider("tiktok", error=ProviderError("provider_unavailable", "TikTok provider unavailable.")),
    }
    monkeypatch.setattr(service, "_providers_by_platform", lambda: providers)
    payload = RefreshRequest(handle_ids=[instagram["id"], tiktok["id"]], confirmed=True)
    run = service.runtime.create_run("test", payload.model_dump(mode="json"))
    result = service.execute_refresh(run["id"], payload)

    assert result["status"] == "Completed with warnings"
    assert len(service.list_posts()) == 1
    assert any("Instagram completed successfully" in event["message"] for event in service.runtime.events(run["id"]))


def test_circuit_breaker_opens_and_requires_confirmation_to_resume(repository: RepositoryService) -> None:
    circuit = CircuitBreakerService(repository)
    for _ in range(3):
        state = circuit.record_error(ProviderError("provider_unavailable", "Provider unavailable."))
    assert state["circuit_state"] == "Open"
    with pytest.raises(Exception, match="explicit confirmation"):
        circuit.resume(confirmed=False)
    assert circuit.resume(confirmed=True)["circuit_state"] == "Half-open"

    auth = circuit.record_error(ProviderError("authentication", "Invalid token."))
    assert auth["circuit_state"] == "Open"
    assert auth["manual_action_required"] is True


def test_cancellation_and_worker_restart_recovery(repository: RepositoryService) -> None:
    runtime = AgentRuntimeService(repository)
    run = runtime.create_run("refresh", {})
    assert runtime.cancel(run["id"])["cancel_requested"] is True

    other = runtime.create_run("refresh", {})
    records = repository.read_json("app-data/agent_runs.json", [])
    for record in records:
        if record["id"] == other["id"]:
            record["started_at"] = (datetime.now(UTC) - timedelta(minutes=31)).isoformat()
    repository.write_json("app-data/agent_runs.json", records)
    recovered_runtime = AgentRuntimeService(repository)
    assert recovered_runtime.get_run(other["id"])["status"] == "Failed"
    assert any(event["kind"] == "recovery" for event in recovered_runtime.events(other["id"]))


def test_local_scheduler_records_safe_skip_without_provider_call(repository: RepositoryService) -> None:
    service = _enable_provider(repository)
    service.budget.update_settings(BudgetSettings(enable_paid_provider_calls=True, schedule_enabled=True))
    service.add_handle(MonitoredHandleInput(platform="instagram", username="scheduled"))
    result = SocialIntelligenceScheduler(service).run_due()
    assert result is not None
    assert result["status"] == "Budget stopped"
    assert any("Scheduled refresh skipped" in item for item in result["warnings"])
    assert service.list_posts() == []


def test_provider_connection_status_records_last_test_without_returning_token(repository: RepositoryService) -> None:
    service = _enable_provider(repository)
    result = service.test_apify_connection(provider_factory=lambda values: FakeProvider("instagram"))
    assert result["connected"] is True
    status = service.secrets.get_provider_configuration_status()
    assert status["last_tested_at"] is not None
    assert status["connection_status"] == "Configured"
    assert "apify_test_token_1234" not in json.dumps(status)


def test_secrets_paths_are_ignored_by_git_rules(repository: RepositoryService) -> None:
    source_root = Path(__file__).resolve().parents[3]
    ignore = (source_root / ".gitignore").read_text(encoding="utf-8")
    assert "app-data/secrets/" in ignore
    assert "app-data/secrets/.env.local" in ignore
    assert ".env.local" in ignore
    assert "APIFY_API_TOKEN=" in (source_root / ".env.example").read_text(encoding="utf-8")
