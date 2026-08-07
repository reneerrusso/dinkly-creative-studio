from __future__ import annotations

import base64
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.backend.models.generation_engine import (
    GenerationRequest,
    ImageGenerationSettings,
    ModelCompareRequest,
    RepairRequest,
    StoryBrief,
)
from app.backend.providers.image_provider import (
    GeminiImageProvider,
    ImageProvider,
    ImageProviderError,
    ImageResult,
)
from app.backend.services.concept_service import ConceptService
from app.backend.services.generation_engine_service import (
    GenerationCancellationRequested,
    GenerationEngineService,
)
from app.backend.services.image_model_registry import ImageModelRegistry
from app.backend.services.prompt_service import PromptService
from app.backend.services.repository_service import RepositoryError, RepositoryService

SOURCE_ROOT = Path(__file__).resolve().parents[3]
VALID_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAIAAAAmkwkpAAAAE0lEQVR4nGP8+eIQAwwwwVl4OQCFEQKrv1CpYwAAAABJRU5ErkJggg=="
)


class FakeImageProvider(ImageProvider):
    def __init__(self, registry: ImageModelRegistry, *, fail_on: set[int] | None = None) -> None:
        self.registry = registry
        self.calls = 0
        self.fail_on = fail_on or set()

    def generate(self, **kwargs: Any) -> ImageResult:
        self.calls += 1
        if self.calls in self.fail_on:
            raise ImageProviderError("one bounded candidate failed", code="rate_limit", retryable=True)
        return ImageResult(VALID_PNG, "image/png", 25)

    def edit(self, **kwargs: Any) -> ImageResult:
        self.calls += 1
        return ImageResult(VALID_PNG, "image/png", 30)

    def health_check(self) -> dict[str, Any]:
        return {"status": "Connected", "connected": True}

    def estimate_cost(self, *, model_key: str, image_size: str | None = None) -> float | None:
        return self.registry.get(model_key)["estimated_output_cost_usd"]["1K"]

    def get_model_info(self, model_key: str) -> dict[str, Any]:
        return self.registry.get(model_key)

    def get_usage(self) -> dict[str, Any]:
        return {}

    def analyze(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "summary": "Best character consistency and scene alignment.",
            "findings": [
                {"category": "CHARACTER", "check": "Dinko exactly two hair tufts", "status": "Pass", "detail": "Correct."},
                {"category": "CHARACTER", "check": "No visible legs", "status": "Pass", "detail": "Correct."},
                {"category": "SCENE", "check": "Shared background", "status": "Pass", "detail": "One continuous pastel."},
            ],
            "runtime_ms": 10,
        }


class FailingRepairProvider(FakeImageProvider):
    def edit(self, **kwargs: Any) -> ImageResult:
        raise ImageProviderError("bounded repair failure", code="timeout", retryable=True)


@pytest.fixture
def engine(repository: RepositoryService, monkeypatch: pytest.MonkeyPatch) -> tuple[GenerationEngineService, FakeImageProvider]:
    for relative in ("CHARACTER_BIBLE.md", "FAILURES.md", "STORY_LIBRARY.md"):
        shutil.copy2(SOURCE_ROOT / relative, repository.path(relative))
    shutil.copy2(SOURCE_ROOT / "references" / "dinkly_young.png", repository.path("references/dinkly_young.png"))
    shutil.copy2(SOURCE_ROOT / "data" / "story_library_v2.json", repository.path("data/story_library_v2.json"))
    registry = ImageModelRegistry()
    provider = FakeImageProvider(registry)
    service = GenerationEngineService(
        repository,
        PromptService(repository, ConceptService(repository)),
        provider_factory=lambda: provider,
    )
    service.secrets.configure_gemini("test-gemini-key")
    service.update_settings(
        ImageGenerationSettings(
            enable_paid_generation=True,
            maximum_cost_per_run=5,
            daily_image_budget=20,
            monthly_image_budget=100,
        )
    )
    return service, provider


def coffee_brief() -> StoryBrief:
    return StoryBrief(
        id="story-coffee",
        format="x-with-you",
        title_left="COFFEE",
        title_right="COFFEE WITH YOU",
        left_action="Dinko drinks coffee alone.",
        left_setting="a rounded breakfast nook",
        left_props=["one proportional mug"],
        right_action="Dinko and Dinka share coffee together.",
        right_setting="the same rounded breakfast nook",
        right_props=["two proportional mugs"],
        shared_environment="One continuous warm cream breakfast nook across both panels.",
        environmental_contrast="The same routine becomes warmer through togetherness.",
        execution_risks=["Keep mugs proportional."],
    )


def test_model_registry_and_selection_rules() -> None:
    registry = ImageModelRegistry()
    assert registry.get("nano_banana_2_lite")["model_id"] == "gemini-3.1-flash-lite-image"
    assert registry.get("nano_banana_2")["model_id"] == "gemini-3.1-flash-image"
    assert registry.get("nano_banana_pro")["model_id"] == "gemini-3-pro-image"
    assert [model["power_label"] for model in registry.list()] == ["FAST", "BALANCED", "MAX"]
    assert [model["power_level"] for model in registry.list()] == [1, 2, 3]
    assert all(model["description"] and model["recommended_for"] for model in registry.list())
    boy_only = coffee_brief().model_copy(update={"right_characters": ["boy"]})
    assert registry.select(boy_only, "automatic", reference_count=1)[0] == "nano_banana_2_lite"
    assert registry.select(coffee_brief(), "automatic", reference_count=2)[0] == "nano_banana_2"
    assert registry.select(coffee_brief(), "lite", reference_count=2)[0] == "nano_banana_2_lite"
    assert registry.select(coffee_brief(), "balanced", reference_count=2)[0] == "nano_banana_2"
    with pytest.raises(RepositoryError, match="confirmation"):
        registry.select(coffee_brief(), "pro", reference_count=2)
    assert registry.select(coffee_brief(), "pro", reference_count=2, allow_pro=True)[0] == "nano_banana_pro"


def test_four_candidates_qa_ranking_approval_history_and_prompt_hiding(engine) -> None:
    service, _ = engine
    service.repository.write_json("data/existing-content.json", {"preserve": True})
    run = service.start(GenerationRequest(story_brief=coffee_brief(), candidate_count=4))
    assert run["selected_model"] == "nano_banana_2"
    assert run["estimated_cost"] > 0
    assert "prompt" not in run["prompt_record"]
    service.execute(run["id"])
    completed = service.get(run["id"])
    assert len(completed["candidates"]) == 4
    assert all(item["qa_status"] == "Pass" for item in completed["candidates"])
    assert all(service.repository.path(item["image_path"]).is_file() for item in completed["candidates"])
    assert service.repository.path(f"app-data/generation-engine/runs/{run['id']}/metadata.json").is_file()
    recommended = next(item for item in completed["candidates"] if item["recommended"])
    service.select_candidate(recommended["id"])
    approved = service.approve(run["id"], "Renee")
    assert approved["status"] == "approved"
    assert approved["final_asset_url"].startswith("/generation-assets/runs/")
    assert approved["original_image_path"] == recommended["image_path"]
    assert approved["final_layout"]["validated"] is True
    assert approved["final_layout"]["original_share"] == 0.8
    assert approved["final_layout"]["extension_share"] == 0.2
    assert approved["final_layout"]["final_width"] == 5
    assert approved["final_layout"]["final_height"] == 4
    assert service.repository.path(approved["final_image_path"]).read_bytes().startswith(b"\x89PNG")
    assert service.history()[0]["id"] == run["id"]
    used = service.repository.read_json("data/used_storylines.json", [])
    assert used[0]["generation_ids"] == [run["id"]]
    assert service.repository.read_json("data/existing-content.json", {}) == {"preserve": True}


def test_download_exports_and_safe_paths(engine) -> None:
    service, _ = engine
    run = service.start(GenerationRequest(story_brief=coffee_brief(), candidate_count=2))
    service.execute(run["id"])
    generated = service.get(run["id"])
    service.select_candidate(generated["candidates"][0]["id"])
    approved = service.approve(run["id"], "Renee")

    png = service.download_final(run["id"], "png")
    assert png.media_type == "image/png"
    assert png.path.read_bytes().startswith(b"\x89PNG")
    assert png.filename.startswith("dinkly-coffee-with-you-")
    duplicate = service.download_final(run["id"], "png")
    assert duplicate.filename != png.filename

    jpg = service.download_final(run["id"], "jpg")
    assert jpg.media_type == "image/jpeg"
    assert jpg.path.read_bytes().startswith(b"\xff\xd8")

    candidates = service.download_candidates(run["id"])
    assert candidates.media_type == "application/zip"
    with zipfile.ZipFile(candidates.path) as bundle:
        names = bundle.namelist()
    assert names == [
        "dinkly-coffee-with-you-candidate-a.png",
        "dinkly-coffee-with-you-candidate-b.png",
    ]

    qa = service.download_qa(run["id"])
    qa_payload = json.loads(qa.path.read_text(encoding="utf-8"))
    assert qa.media_type == "application/json"
    assert len(qa_payload["candidates"]) == 2
    summary = service.download_summary(run["id"])
    summary_payload = json.loads(summary.path.read_text(encoding="utf-8"))
    assert summary_payload["status"] == "APPROVED"
    assert summary_payload["model"]["power_label"] == "BALANCED"
    assert "model_id" not in summary_payload["model"]
    assert "prompt" not in summary_payload

    raw = service._load_run(run["id"])
    original_path = raw["final_image_path"]
    raw["final_image_path"] = "README.md"
    service._save_run(raw)
    with pytest.raises(RepositoryError, match="outside"):
        service.download_final(run["id"], "png")
    raw["final_image_path"] = original_path
    service._save_run(raw)
    with pytest.raises(RepositoryError, match="format"):
        service.download_final(run["id"], "svg")
    assert approved["status"] == "approved"


def test_five_comic_individual_and_zip_exports(engine) -> None:
    service, _ = engine
    run = service.start(GenerationRequest(story_brief=coffee_brief(), candidate_count=1))
    service.execute(run["id"])
    candidate = service.get(run["id"])["candidates"][0]
    service.select_candidate(candidate["id"])
    service.approve(run["id"], "Renee")
    raw = service._load_run(run["id"])
    source = service.repository.path(raw["final_image_path"])
    comic_paths = []
    for index in range(1, 6):
        target = source.parent / f"comic-{index:02d}.png"
        shutil.copy2(source, target)
        comic_paths.append(service.repository.relative(target))
    raw["story_format"] = "five-comic"
    raw["story_brief"]["title_right"] = "OUR PLACE"
    raw["comic_asset_paths"] = comic_paths
    service._save_run(raw)

    comic = service.download_final(run["id"], "png", comic_number=3)
    assert comic.filename.startswith("dinkly-our-place-comic-03")
    archive = service.download_all_comics(run["id"])
    with zipfile.ZipFile(archive.path) as bundle:
        assert bundle.namelist() == [f"dinkly-our-place-comic-{index:02d}.png" for index in range(1, 6)]


def test_partial_candidate_failure_preserves_successes(repository: RepositoryService) -> None:
    for relative in ("CHARACTER_BIBLE.md", "FAILURES.md", "STORY_LIBRARY.md"):
        shutil.copy2(SOURCE_ROOT / relative, repository.path(relative))
    shutil.copy2(SOURCE_ROOT / "references" / "dinkly_young.png", repository.path("references/dinkly_young.png"))
    shutil.copy2(SOURCE_ROOT / "data" / "story_library_v2.json", repository.path("data/story_library_v2.json"))
    provider = FakeImageProvider(ImageModelRegistry(), fail_on={2})
    service = GenerationEngineService(repository, PromptService(repository, ConceptService(repository)), provider_factory=lambda: provider)
    service.secrets.configure_gemini("test-gemini-key")
    service.update_settings(ImageGenerationSettings(enable_paid_generation=True, maximum_cost_per_run=5, daily_image_budget=20, monthly_image_budget=100))
    run = service.start(GenerationRequest(story_brief=coffee_brief(), candidate_count=4))
    service.execute(run["id"])
    completed = service.get(run["id"])
    assert completed["status"] == "awaiting_human"
    assert sum(bool(item["image_path"]) for item in completed["candidates"]) == 3
    failed = next(item for item in completed["candidates"] if item.get("error"))
    assert failed["error"]["retryable"]
    retried = service.retry_candidate(failed["id"])
    retry = next(item for item in retried["candidates"] if item.get("retry_parent_id") == failed["id"])
    assert service.repository.path(retry["image_path"]).is_file()
    assert failed["id"] in {item["id"] for item in retried["candidates"]}


def test_cancellation_between_candidates_preserves_completed_and_stops_paid_calls(engine) -> None:
    service, provider = engine
    run = service.start(GenerationRequest(story_brief=coffee_brief(), candidate_count=4))
    checks = 0

    def should_cancel() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 7

    with pytest.raises(GenerationCancellationRequested):
        service.execute(run["id"], should_cancel=should_cancel)
    cancelled = service.get(run["id"])
    assert cancelled["status"] == "cancelled"
    assert provider.calls == 2
    assert len(cancelled["candidates"]) == 2
    assert cancelled["cancellation_stage"] == "Candidate 2 of 4"


def test_cancellation_during_provider_call_discards_returned_result(engine) -> None:
    service, provider = engine
    run = service.start(GenerationRequest(story_brief=coffee_brief(), candidate_count=4))
    with pytest.raises(GenerationCancellationRequested):
        service.execute(run["id"], should_cancel=lambda: provider.calls >= 1)
    cancelled = service.get(run["id"])
    assert provider.calls == 1
    assert cancelled["candidates"] == []
    assert cancelled["status"] == "cancelled"


def test_cancellation_before_manual_qa_and_repair_starts_no_provider_call(engine) -> None:
    service, provider = engine
    run = service.start(GenerationRequest(story_brief=coffee_brief(), candidate_count=1))
    service.execute(run["id"])
    candidate = service.get(run["id"])["candidates"][0]
    prior_calls = provider.calls
    with pytest.raises(GenerationCancellationRequested):
        service.qa_candidate(candidate["id"], should_cancel=lambda: True)
    assert provider.calls == prior_calls

    second = service.start(GenerationRequest(story_brief=coffee_brief(), candidate_count=1))
    service.execute(second["id"])
    candidate = service.get(second["id"])["candidates"][0]
    prior_calls = provider.calls
    with pytest.raises(GenerationCancellationRequested):
        service.repair(candidate["id"], RepairRequest(failures=["Oversized mug"]), should_cancel=lambda: True)
    assert provider.calls == prior_calls


def test_persisted_loader_events_replay_real_candidate_and_qa_progress(engine) -> None:
    service, _ = engine
    run = service.start(GenerationRequest(story_brief=coffee_brief(), candidate_count=2))
    service.execute(run["id"])
    events = service.events(run["id"])
    progress = [event for event in events if event["kind"] == "progress"]
    stages = {event["data"].get("stage") for event in progress}
    assert {"story", "compile", "references", "generate", "qa", "repair", "human_review"} <= stages
    assert any(
        event["data"].get("stage") == "generate"
        and event["data"].get("candidate") == "A"
        and "Nano Banana 2" in event["message"]
        for event in progress
    )
    assert any(
        event["data"].get("stage") == "qa"
        and event["data"].get("candidate") == "B"
        and event["data"].get("candidate_status") == "complete"
        for event in progress
    )
    first = events[4]
    assert service.events(run["id"], first["id"]) == events[5:]
    public_run = service.get(run["id"])
    assert public_run["selected_model_info"]["power_label"] == "BALANCED"
    assert "model_id" not in public_run["selected_model_info"]


def test_history_hydrates_model_power_for_legacy_candidates(engine) -> None:
    service, _ = engine
    run = service.start(GenerationRequest(story_brief=coffee_brief(), candidate_count=1))
    service.execute(run["id"])
    raw = service._load_run(run["id"])
    candidate = raw["candidates"][0]
    for field in (
        "model_display_name",
        "model_power_label",
        "model_power_level",
        "model_description",
        "model_cost_tier",
    ):
        candidate.pop(field, None)
    service._save_run(raw)

    legacy_run = service.get(run["id"])
    legacy_candidate = legacy_run["candidates"][0]
    assert legacy_candidate["model_display_name"] == "Nano Banana 2"
    assert legacy_candidate["model_power_label"] == "BALANCED"
    assert legacy_candidate["model_power_level"] == 2


def test_repair_lineage_and_escalation(engine) -> None:
    service, _ = engine
    run = service.start(GenerationRequest(story_brief=coffee_brief(), candidate_count=1))
    service.execute(run["id"])
    candidate = service.get(run["id"])["candidates"][0]
    candidate = service.qa_candidate(candidate["id"], [{"category": "PROP SCALE", "check": "Oversized prop", "status": "Warning", "detail": "Mug too large."}])
    repaired = service.repair(candidate["id"], RepairRequest(failures=["Oversized prop"]))
    child = next(item for item in repaired["candidates"] if item.get("repair_parent_id") == candidate["id"])
    assert child["repair_number"] == 1
    assert child["image_path"].startswith(f"app-data/generation-engine/runs/{run['id']}/repairs/")
    service.qa_candidate(
        child["id"],
        [{"category": "CHARACTER", "check": "Eye drift", "status": "Warning", "detail": "Recheck eyes."}],
    )
    second = service.repair(
        child["id"],
        RepairRequest(failures=["Eye drift"], model_selection="balanced"),
    )
    grandchild = next(item for item in second["candidates"] if item.get("repair_parent_id") == child["id"])
    assert grandchild["repair_number"] == 2
    assert grandchild["model"] == "nano_banana_2"
    progress = [event for event in service.events(run["id"]) if event["kind"] == "progress"]
    repair_steps = {event["data"].get("repair_step") for event in progress}
    assert {"preparing_edit", "submitting_repair", "repair_received", "running_qa", "complete"} <= repair_steps


def test_repair_failure_preserves_original_and_returns_to_checkpoint(engine) -> None:
    service, _ = engine
    run = service.start(GenerationRequest(story_brief=coffee_brief(), candidate_count=1))
    service.execute(run["id"])
    original = service.get(run["id"])["candidates"][0]
    service.provider_factory = lambda: FailingRepairProvider(ImageModelRegistry())
    with pytest.raises(RepositoryError, match="Repair failed"):
        service.repair(original["id"], RepairRequest(failures=["Oversized mug"]))
    preserved = service.get(run["id"])
    assert preserved["status"] == "awaiting_human"
    assert preserved["candidates"][0]["image_path"] == original["image_path"]
    assert preserved["candidates"][0]["repair_failures"][0]["code"] == "timeout"


def test_gemini_provider_classifies_common_failures_without_network() -> None:
    provider = GeminiImageProvider("", ImageModelRegistry())
    with pytest.raises(ImageProviderError) as missing:
        provider._post("nano_banana_2_lite", {})
    assert missing.value.code == "missing_key"

    request = httpx.Request("POST", "https://generativelanguage.googleapis.com")
    invalid = provider._provider_error(
        httpx.Response(403, request=request, json={"error": {"message": "API key invalid"}})
    )
    limited = provider._provider_error(
        httpx.Response(429, request=request, json={"error": {"message": "quota reached"}})
    )
    unavailable = provider._provider_error(
        httpx.Response(404, request=request, json={"error": {"message": "model missing"}})
    )
    assert invalid.code == "invalid_key"
    assert limited.code == "rate_limit" and limited.retryable
    assert unavailable.code == "model_unavailable"


def test_model_comparison_records_measured_differences(engine) -> None:
    service, _ = engine
    run = service.compare_models(ModelCompareRequest(story_brief=coffee_brief()))
    service.execute_comparison(run["id"])
    completed = service.get(run["id"])
    assert {item["model"] for item in completed["candidates"]} == {"nano_banana_2_lite", "nano_banana_2"}
    assert all(item["runtime_ms"] is not None for item in completed["candidates"])
    stats = service.model_stats()
    assert next(item for item in stats if item["model"] == "nano_banana_2_lite")["sample_size"] == 1


def test_missing_key_blocks_real_generation(engine, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _ = engine
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    service.secrets.remove_gemini()
    with pytest.raises(RepositoryError, match="GEMINI_API_KEY"):
        service.start(GenerationRequest(story_brief=coffee_brief()))


def test_reference_versions_and_story_library_handoff(engine) -> None:
    service, _ = engine
    brief = service.build_brief(type("Request", (), {"story_brief": None, "story_id": "story-v2-party", "concept_text": None})())
    assert brief["source"] == "story_library"
    manifest = service.reference_manifest(StoryBrief.model_validate(brief["story_brief"]))
    assert manifest["dinko_reference_version"]
    assert manifest["dinka_reference_version"]
