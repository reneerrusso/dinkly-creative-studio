from __future__ import annotations

from pathlib import Path

from app.backend.config import Settings
from app.backend.services.learning_engine import BrainProposalService, LearningCostGuardrail
from app.backend.services.memory_service import MemoryExtractor, MemoryService
from app.backend.services.repository_service import RepositoryService


def repository(tmp_path: Path) -> RepositoryService:
    return RepositoryService(
        Settings(
            repository_root=tmp_path,
            frontend_origin="http://127.0.0.1:3000",
            max_upload_bytes=1024,
        )
    )


def test_memory_extractor_separates_temporary_context_from_preference(tmp_path: Path) -> None:
    service = MemoryService(repository(tmp_path))
    assert service.extract_and_store(
        "Generate number 4.", source_type="web", source_id="message-1"
    ) is None
    stored = service.extract_and_store(
        "Stop giving me so many couch scenes.", source_type="slack", source_id="message-2"
    )
    assert stored and stored["memory_type"] == "creative_preference"


def test_memory_persists_across_service_restart_and_answers_with_refs(tmp_path: Path) -> None:
    first = MemoryService(repository(tmp_path))
    stored = first.extract_and_store(
        "Always keep coffee mugs smaller than the character face.",
        source_type="qa_feedback",
        source_id="qa-1",
        evidence_ids=["generation-1", "generation-2"],
    )
    second = MemoryService(repository(tmp_path))
    answer = second.answer("What do you know about coffee mugs?")
    assert stored and stored["id"] in answer["memory_refs"]
    assert "coffee mugs" in answer["answer"].lower()


def test_brain_proposal_requires_evidence_and_human_approval(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    (tmp_path / "NANO_BANANA_RULES.md").write_text("# Rules\n", encoding="utf-8")
    memory = MemoryService(repo).extract_and_store(
        "Always keep coffee mugs smaller than the DINKLY face.",
        source_type="qa_feedback",
        source_id="qa-1",
        evidence_ids=["generation-1", "generation-2"],
    )
    assert memory
    proposals = BrainProposalService(repo)
    proposal = proposals.propose_from_memory(memory["id"], target_file="NANO_BANANA_RULES.md")
    assert "coffee mugs" not in (tmp_path / "NANO_BANANA_RULES.md").read_text(encoding="utf-8")
    approved = proposals.decide(
        proposal["id"], decision="approve", edited_rule=None, reviewed_by="Renee"
    )
    assert approved["application_status"] == "applied_locally"
    assert "coffee mugs" in (tmp_path / "NANO_BANANA_RULES.md").read_text(encoding="utf-8")


def test_learning_cost_guardrail_defers_without_losing_records(tmp_path: Path) -> None:
    repo = RepositoryService(
        Settings(
            repository_root=tmp_path,
            frontend_origin="http://127.0.0.1:3000",
            max_upload_bytes=1024,
            learning_maximum_cost_per_task=0.1,
            learning_daily_budget=0.2,
            learning_monthly_budget=0.3,
        )
    )
    result = LearningCostGuardrail(repo).preflight("learning-1", 0.5)
    assert result["allowed"] is False
    assert "maximum AI spend per learning task reached" in result["reasons"]


def test_classifier_contract() -> None:
    extractor = MemoryExtractor()
    assert extractor.classify("That one, number two") == "temporary_context"
    assert extractor.classify("Four generations had oversized mugs again") == "production_learning"
