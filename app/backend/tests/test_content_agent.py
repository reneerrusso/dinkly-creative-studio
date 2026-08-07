from __future__ import annotations

from datetime import datetime

import pytest

from app.backend.models.content_agent import ContentSettings
from app.backend.services.content_agent import DevelopmentFixtureProvider, UnavailableContentModelProvider
from app.backend.services.content_agent_scheduler import ContentAgentScheduler
from app.backend.services.content_agent_service import ContentAgentService
from app.backend.services.content_agent_workflow import ConceptGeneratorWorkflow, _normalize, _similarity
from app.backend.services.repository_service import RepositoryError, RepositoryService


def generate_batch(service: ContentAgentService, mode: str = "primary") -> dict:
    started = service.start_batch(mode)
    service.execute_batch(started["run"]["id"], started["batch"]["id"], mode)
    return started


def test_daily_batch_has_exactly_ten_finalists_per_format(repository: RepositoryService) -> None:
    service = ContentAgentService(repository, DevelopmentFixtureProvider())
    started = generate_batch(service)
    concepts = [item for item in service.list_concepts() if item["batch_id"] == started["batch"]["id"]]
    assert len(concepts) == 30
    assert {name: sum(item["format"] == name for item in concepts) for name in ("with_you", "before_after", "five_story")} == {"with_you": 10, "before_after": 10, "five_story": 10}
    assert all(len(item["comics"]) == 5 for item in concepts if item["format"] == "five_story")
    events = service.runtime.events(started["run"]["id"])
    assert any(item["kind"] == "deduplicate" for item in events)
    assert events[-1]["message"] == "Daily Concept Generator batch complete."


def test_missing_provider_and_primary_batch_uniqueness(repository: RepositoryService) -> None:
    service = ContentAgentService(repository, UnavailableContentModelProvider())
    with pytest.raises(RepositoryError, match="No AI provider configured"):
        service.start_batch()
    fixture = ContentAgentService(repository, DevelopmentFixtureProvider())
    fixture.start_batch()
    with pytest.raises(RepositoryError, match="already has a primary batch"):
        fixture.start_batch()


def test_approval_pass_chat_replacement_queue_prompt_and_used_flow(repository: RepositoryService) -> None:
    service = ContentAgentService(repository, DevelopmentFixtureProvider())
    generate_batch(service)
    concepts = service.list_concepts()
    with_you = next(item for item in concepts if item["format"] == "with_you")
    passed = next(item for item in concepts if item["format"] == "before_after")
    five = next(item for item in concepts if item["format"] == "five_story")
    replacement_target = [item for item in concepts if item["format"] == "with_you"][1]

    approved_with_you = service.approve(with_you["id"])
    assert approved_with_you["status"] == "approved"
    saved_stories = repository.read_json("app-data/story_library.json", [])
    saved_story = next(item for item in saved_stories if item["source_concept_id"] == with_you["id"])
    assert approved_with_you["story_library_id"] == saved_story["id"]
    assert saved_story["status"] == "Approved"
    assert saved_story["added_to_library_at"]
    service.story_library.add_approved_concept(approved_with_you)
    assert sum(item.get("source_concept_id") == with_you["id"] for item in repository.read_json("app-data/story_library.json", [])) == 1
    assert service.pass_concept(passed["id"], "Too repetitive")["status"] == "passed"
    state_after_review = service.state()
    assert any(item["id"] == with_you["id"] for item in state_after_review["production_queue"])
    assert all(item["id"] != with_you["id"] for item in state_after_review["today_concepts"])
    assert any(item["id"] == passed["id"] for item in state_after_review["passed"])
    assert service.chat("Stop giving me coffee ideas.")["preference"]["preference_type"] == "avoid"
    replacement = service.replace(replacement_target["id"])
    assert replacement["slot"] == replacement_target["slot"]
    assert service.get_concept(replacement_target["id"])["status"] == "archived"

    single_handoff = service.prompt_handoff(with_you["id"])
    assert single_handoff["kind"] == "single"
    assert single_handoff["handoff_agent"] == "prompt-agent"
    assert "source=concept-generator" in single_handoff["href"]
    assert "autogenerate=1" in single_handoff["href"]
    assert with_you["left_action"] in single_handoff["prompt"]["prompt"]
    assert service.get_concept(with_you["id"])["status"] == "used"
    assert service.approve(five["id"])["status"] == "approved"
    story_handoff = service.prompt_handoff(five["id"])
    assert story_handoff["kind"] == "five_story"
    assert len(story_handoff["prompts"]) == 5
    assert len(set(story_handoff["prompt_ids"])) == 5
    for beat, generated in zip(five["comics"], story_handoff["prompts"], strict=True):
        assert beat["scene"] in generated["prompt"]
    assert service.get_concept(five["id"])["status"] == "used"

    used = service.mark_used(with_you["id"])
    assert used["status"] == "used"
    state = service.state()
    assert all(item["id"] != with_you["id"] for item in state["production_queue"])
    assert any(item["concept"]["id"] == with_you["id"] for item in state["used_storylines"])


def test_approval_limit_and_supplemental_batch_preserves_approved(repository: RepositoryService) -> None:
    service = ContentAgentService(repository, DevelopmentFixtureProvider())
    generate_batch(service)
    candidates = [item for item in service.list_concepts() if item["format"] == "with_you"]
    for item in candidates[:5]:
        service.approve(item["id"])
    with pytest.raises(RepositoryError, match="already selected 5"):
        service.approve(candidates[5]["id"])
    approved_ids = {item["id"] for item in service.list_concepts() if item["status"] == "approved"}
    service.start_batch("supplemental")
    assert approved_ids <= {item["id"] for item in service.list_concepts() if item["status"] == "approved"}


def test_scheduler_is_off_by_default_and_records_missing_provider(repository: RepositoryService) -> None:
    service = ContentAgentService(repository, UnavailableContentModelProvider())
    scheduler = ContentAgentScheduler(service)
    assert scheduler.run_due(datetime(2026, 8, 6, 9, 0, tzinfo=scheduler.timezone)) is None
    service.update_settings(ContentSettings(generate_daily_automatically=True, run_time="08:00"))
    result = scheduler.run_due(datetime(2026, 8, 6, 9, 0, tzinfo=scheduler.timezone))
    assert result and result["status"] == "skipped"


def test_invalid_model_output_has_one_bounded_validation_safe_retry(repository: RepositoryService) -> None:
    class RetryProvider(DevelopmentFixtureProvider):
        def __init__(self) -> None:
            self.calls: dict[str, int] = {}

        def generate_candidates(self, content_format, brief, count):
            key = content_format.value
            self.calls[key] = self.calls.get(key, 0) + 1
            if self.calls[key] == 1:
                return [{"format": key, "why_it_may_work": "invalid"}] * count
            return super().generate_candidates(content_format, brief, count)

    provider = RetryProvider()
    service = ContentAgentService(repository, provider)
    started = generate_batch(service)
    assert provider.calls == {"with_you": 2, "before_after": 2, "five_story": 2}
    assert sum(event["kind"] == "validation_retry" for event in service.runtime.events(started["run"]["id"])) == 3


def test_semantic_duplicate_normalization_catches_title_variants() -> None:
    assert _similarity(_normalize("MOVIES WITH YOU"), _normalize("MOVIE NIGHT WITH YOU")) >= 0.5
    assert _normalize("WEEKENDS BEFORE YOU") == _normalize("WEEKEND AFTER YOU")


def test_near_identical_emotional_execution_is_excluded(repository: RepositoryService) -> None:
    service = ContentAgentService(repository, DevelopmentFixtureProvider())
    workflow = ConceptGeneratorWorkflow(repository, service.runtime, service.provider)
    original = {
        "format": "with_you", "title_left": "RAINY ERRANDS", "left_action": "waits alone under an umbrella at a bus stop",
        "left_setting": "covered bus stop", "right_action": "waits under the umbrella as the other brings warm tea",
        "right_setting": "covered bus stop", "emotional_insight": "Being noticed makes a dreary wait feel cared for.",
    }
    renamed = {**original, "title_left": "A GREY-DAY FAVOR"}
    unique, removed = workflow._deduplicate([renamed], workflow._concept_keys(original))
    assert unique == []
    assert removed == 1


def test_new_runs_use_canonical_agent_id_and_old_runs_are_normalized(repository: RepositoryService) -> None:
    service = ContentAgentService(repository, DevelopmentFixtureProvider())
    legacy = service.runtime.create_run("content-daily-batch", {}, agent="content-agent")
    assert service.runtime.get_run(legacy["id"])["display_agent"] == "Concept Generator"
    started = service.start_batch()
    assert started["run"]["agent"] == "concept-generator"
    assert started["run"]["kind"] == "concept-generator-daily-batch"
