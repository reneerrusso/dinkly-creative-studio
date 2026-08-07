from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.backend.services.agent_visual_state_service import AgentVisualStateService, DinklyLearningLoop
from app.backend.services.repository_service import RepositoryError, RepositoryService


def progress(run_id: str, stage: str, status: str, message: str) -> dict:
    return {
        "id": f"event-{stage}-{status}",
        "run_id": run_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "level": "warning" if status == "failed" else "info",
        "kind": "progress",
        "message": message,
        "data": {"stage": stage, "status": status},
    }


@pytest.mark.parametrize(
    ("stage", "status", "expected"),
    [
        ("story", "active", "preparing"),
        ("compile", "active", "preparing"),
        ("references", "active", "preparing"),
        ("generate", "active", "generating"),
        ("qa", "active", "reviewing"),
        ("repair", "active", "repairing"),
        ("repair", "complete", "reviewing"),
        ("human_review", "active", "waiting_for_human"),
        ("human_review", "complete", "success"),
        ("generate", "failed", "error"),
    ],
)
def test_generation_event_to_visual_state_mapping(repository: RepositoryService, stage: str, status: str, expected: str) -> None:
    visual = AgentVisualStateService(repository)
    result = visual.handle_generation_event(progress("generation-123456789abc", stage, status, f"{stage} {status}"))
    assert result["state"] == expected
    assert result["last_event"] == f"{stage} {status}"


def test_idle_state_and_state_restoration_after_reconnect(repository: RepositoryService) -> None:
    visual = AgentVisualStateService(repository)
    assert visual.status()["state"] == "idle"
    visual.transition("generating", "Creating Candidate 2 of 4 with Nano Banana 2.", source_run_id="generation-123456789abc")
    restored = AgentVisualStateService(repository).status()
    assert restored["state"] == "generating"
    assert restored["source_run_id"] == "generation-123456789abc"


def test_success_returns_to_idle_after_truthful_expiry(repository: RepositoryService) -> None:
    visual = AgentVisualStateService(repository)
    visual.transition("success", "Comic approved.")
    raw = repository.read_json("app-data/dinkly-agent/state.json", {})
    raw["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    repository.write_json("app-data/dinkly-agent/state.json", raw)
    assert visual.status()["state"] == "idle"


def test_expression_image_and_one_image_fallback(repository: RepositoryService) -> None:
    visual = AgentVisualStateService(repository)
    fallback = visual.expression_for("learning")
    assert fallback["custom"] is False
    assert fallback["path"] == "/agents/social-intelligence.png"
    png = b"\x89PNG\r\n\x1a\n" + b"approved-expression"
    custom = visual.save_expression("learning", png)
    assert custom["custom"] is True
    assert custom["path"] == "/agents/dinkly-agent/learning.png"
    with pytest.raises(RepositoryError, match="PNG"):
        visual.save_expression("error", b"not-an-image")


def test_learning_loop_with_no_changes_stays_idle_and_makes_no_provider_call(repository: RepositoryService) -> None:
    visual = AgentVisualStateService(repository)
    loop = DinklyLearningLoop(repository, visual)
    before_events = visual.events()
    result = loop.run()
    assert result == {"ran": False, "reason": "no_changes", "provider_calls": 0, "new_evidence": 0}
    assert visual.status()["state"] == "idle"
    assert visual.events() == before_events


def test_learning_loop_detects_new_approval_and_persists_checkpoint(repository: RepositoryService) -> None:
    visual = AgentVisualStateService(repository)
    loop = DinklyLearningLoop(repository, visual)
    run_id = "generation-111111111111"
    repository.write_json(
        f"app-data/generation-engine/runs/{run_id}/metadata.json",
        {
            "id": run_id,
            "status": "approved",
            "approved_at": datetime.now(UTC).isoformat(),
            "story_brief": {"left_props": ["mug"], "right_props": ["mug", "chair"]},
            "candidates": [],
        },
    )
    result = loop.run()
    assert result["ran"] is True
    assert result["provider_calls"] == 0
    assert result["counts"]["approval"] == 1
    assert any("three or fewer" in item["statement"] for item in result["learnings"])
    checkpoint = repository.read_json("app-data/dinkly-agent/learning-checkpoint.json", {})
    assert checkpoint["provider_calls"] == 0
    assert any(item.startswith(f"approval:{run_id}") for item in checkpoint["seen_evidence_ids"])
    assert any(event["state"] == "learning" for event in visual.events())


def test_learning_loop_detects_qa_failure_without_calling_provider(repository: RepositoryService) -> None:
    visual = AgentVisualStateService(repository)
    loop = DinklyLearningLoop(repository, visual)
    run_id = "generation-222222222222"
    repository.write_json(
        f"app-data/generation-engine/runs/{run_id}/metadata.json",
        {
            "id": run_id,
            "status": "awaiting_human",
            "candidates": [
                {
                    "id": "candidate-a",
                    "qa_findings": [
                        {"check": "Oversized mug scale", "status": "Fail", "detail": "Mug is larger than Dinko's face."}
                    ],
                }
            ],
        },
    )
    result = loop.run()
    assert result["provider_calls"] == 0
    assert result["counts"]["qa_failure"] == 1
    assert any("mug scale" in item["statement"] for item in repository.read_json("data/qa_learnings.json", []))


@pytest.mark.parametrize(
    ("message", "topic", "direction"),
    [
        ("Less couch content.", "couch concepts", "less"),
        ("Use Girl alone more often.", "Girl alone on the left", "more"),
        ("Stop making the props so big.", "prop scale", "less"),
        ("Keep backgrounds simpler.", "simple backgrounds", "more"),
        ("I liked Candidate C.", "Candidate C qualities", "more"),
    ],
)
def test_chat_feedback_creates_structured_preference(repository: RepositoryService, message: str, topic: str, direction: str) -> None:
    visual = AgentVisualStateService(repository)
    loop = DinklyLearningLoop(repository, visual)
    result = loop.save_chat_preference(message)
    assert result["preference"]["learning_type"] == "user_preference"
    assert result["preference"]["topic"] == topic
    assert result["preference"]["direction"] == direction
    assert result["preference"]["confidence"] == "high"
    assert "Got it" in result["reply"]
    assert any(event["state"] == "learning" for event in visual.events())

