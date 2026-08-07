#!/usr/bin/env python3
"""Run a labeled no-network Social Intelligence demonstration in a temporary repository."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend.config import Settings  # noqa: E402
from app.backend.models.social_intelligence import (  # noqa: E402
    BudgetSettings,
    ManualPostInput,
    MonitoredHandleInput,
    RunStatus,
)
from app.backend.providers.social_data import ApifyInstagramProvider  # noqa: E402
from app.backend.services.budget_service import BudgetStopped  # noqa: E402
from app.backend.services.repository_service import RepositoryService  # noqa: E402
from app.backend.services.social_intelligence_service import SocialIntelligenceService  # noqa: E402


def temporary_repository(directory: Path) -> RepositoryService:
    for relative in ("data", "schemas", "app-data", "app-data/sprites", "PROMPT_TEMPLATES"):
        (directory / relative).mkdir(parents=True, exist_ok=True)
    for schema in (ROOT / "schemas").glob("*.schema.json"):
        shutil.copy2(schema, directory / "schemas" / schema.name)
    for name in (
        "social_posts",
        "social_learnings",
        "storyline_scores",
        "approved_prompts",
        "monitored_handles",
        "competitor_profiles",
        "competitor_posts",
        "competitor_snapshots",
        "competitor_learnings",
        "competitor_concept_directions",
        "provider_usage",
    ):
        (directory / "data" / f"{name}.json").write_text("[]\n", encoding="utf-8")
    for name in ("concepts", "prompts", "art_reviews", "story_library", "agent_runs", "agent_events"):
        (directory / "app-data" / f"{name}.json").write_text("[]\n", encoding="utf-8")
    (directory / "app-data" / "provider_states.json").write_text("{}\n", encoding="utf-8")
    (directory / "app-data" / "provider_budget.json").write_text(
        (ROOT / "app-data" / "provider_budget.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return RepositoryService(Settings(directory, "http://127.0.0.1:3000", 2 * 1024 * 1024))


def show(label: str, payload: object) -> None:
    print(f"\n## {label}")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dinkly-social-intelligence-fixture-") as temporary:
        repository = temporary_repository(Path(temporary).resolve())
        service = SocialIntelligenceService(repository)
        show("No-API state", service.providers()[0])

        secret_status = service.secrets.configure_apify("fixture_token_abcd", "fixture~instagram", "fixture~tiktok")
        show("Secure Settings save (fixture token masked)", secret_status)

        def invalid_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="invalid token")

        invalid = ApifyInstagramProvider(
            "fixture_invalid_token",
            "fixture~actor",
            max_retries=0,
            client_factory=lambda **kwargs: httpx.Client(transport=httpx.MockTransport(invalid_handler), **kwargs),
        ).validate_credentials()
        show("Invalid-key failure (mocked transport; no network)", invalid)

        service.budget.update_settings(BudgetSettings(enable_paid_provider_calls=True))
        handle, _ = service.add_handle(MonitoredHandleInput(platform="instagram", username="fixtureaccount"))
        show("Normalized monitored handle", handle)
        show("Budget preflight (conservative local fixture)", service.preflight(_selection(handle["id"])))

        service.budget.update_settings(
            BudgetSettings(
                enable_paid_provider_calls=True,
                daily_provider_budget=2.0,
                monthly_provider_budget=0.2,
                automatically_pause_at_80_percent=False,
            )
        )
        service.budget.record_usage({"provider": "apify", "estimated_cost_before": 0.2, "actual_cost": None})
        try:
            service.budget.check_before_request(0.1, request_count=1, phase="fixture retry")
        except BudgetStopped as exc:
            show("Hard budget stop", {"status": "Budget stopped", "message": str(exc)})

        def credit_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(402, text="insufficient credit")

        credit = ApifyInstagramProvider(
            "fixture_credit_token",
            "fixture~actor",
            max_retries=0,
            client_factory=lambda **kwargs: httpx.Client(transport=httpx.MockTransport(credit_handler), **kwargs),
        ).validate_credentials()
        show("Insufficient-credit response (mocked transport; no network)", credit)

        for post_id, views in (("fixture-1", 100), ("fixture-2", 100), ("fixture-3", 1000)):
            service.add_manual_post(
                ManualPostInput(
                    handle_id=handle["id"],
                    platform="instagram",
                    platform_post_id=post_id,
                    caption="Coffee together at home",
                    view_count=views,
                    like_count=10,
                    comment_count=0,
                    share_count=None,
                    follower_count=1000,
                )
            )
        show("Manual import fallback", {"source": "clearly labeled local fixture", "posts": len(service.list_posts()), "provider_calls": 0})

        analysis = service.analyze_existing_data()
        learning = service.list_learnings()[0]
        direction = service.list_directions()[0]
        handoff = service.open_direction_in_prompt_builder(direction["id"])
        show("Evidence analysis", analysis)
        show("Competitor learning", learning)
        show("Original DINKLY direction", direction)
        show("Prompt Builder handoff", handoff)

        run = service.runtime.create_run("manual-fixture-demonstration", {"fixture": True})
        service.runtime.emit(run["id"], "scope", "Loaded 1 fixture handle from a temporary repository.")
        service.runtime.emit(run["id"], "analysis", "Analyzed 3 manually supplied fixture posts; no provider call was made.")
        service.runtime.finish(run["id"], RunStatus.COMPLETED, {"fixture": True, "posts_analyzed": 3})
        show("Truthful persisted events", service.runtime.events(run["id"]))

    print("\nFixture repository removed. No production data or live provider was touched.")
    return 0


def _selection(handle_id: str):
    from app.backend.models.social_intelligence import HandleSelection

    return HandleSelection(handle_ids=[handle_id])


if __name__ == "__main__":
    raise SystemExit(main())
