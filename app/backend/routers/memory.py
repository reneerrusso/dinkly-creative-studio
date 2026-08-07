from __future__ import annotations

from fastapi import APIRouter, Query

from app.backend.models.memory import (
    BrainProposalCreate,
    BrainProposalDecision,
    MemoryQuestion,
    MemoryUpdate,
    PerformanceSnapshotInput,
)
from app.backend.services.learning_engine import BrainProposalService, PerformanceService
from app.backend.services.memory_service import MemoryService
from app.backend.services.repository_service import RepositoryService

router = APIRouter(tags=["memory"])


def _memory() -> MemoryService:
    return MemoryService(RepositoryService())


@router.get("/api/memory")
def list_memory(
    memory_type: str | None = None,
    active: bool | None = Query(default=True),
    include_inactive: bool = False,
) -> list[dict]:
    return _memory().list(memory_type=memory_type, active=None if include_inactive else active)


@router.post("/api/memory/ask")
def ask_memory(request: MemoryQuestion) -> dict:
    return _memory().answer(request.question)


@router.get("/api/memory/{memory_id}")
def get_memory(memory_id: str) -> dict:
    return _memory().get(memory_id)


@router.put("/api/memory/{memory_id}")
def update_memory(memory_id: str, request: MemoryUpdate) -> dict:
    return _memory().update(memory_id, request.model_dump(exclude_none=True))


@router.post("/api/memory/{memory_id}/deactivate")
def deactivate_memory(memory_id: str) -> dict:
    return _memory().update(memory_id, {"active": False})


@router.delete("/api/memory/{memory_id}")
def delete_memory(memory_id: str) -> dict:
    _memory().delete(memory_id)
    return {"deleted": True, "id": memory_id}


@router.get("/api/brain-update-proposals")
def list_brain_proposals(proposal_status: str | None = Query(default=None, alias="status")) -> list[dict]:
    return BrainProposalService(RepositoryService()).list(status=proposal_status)


@router.post("/api/brain-update-proposals")
def create_brain_proposal(request: BrainProposalCreate) -> dict:
    return BrainProposalService(RepositoryService()).propose_from_memory(
        request.memory_id,
        target_file=request.target_file,
    )


@router.post("/api/brain-update-proposals/{proposal_id}/decision")
def decide_brain_proposal(proposal_id: str, request: BrainProposalDecision) -> dict:
    return BrainProposalService(RepositoryService()).decide(
        proposal_id,
        decision=request.decision,
        edited_rule=request.edited_rule,
        reviewed_by=request.reviewed_by,
    )


@router.post("/api/generation-engine/runs/{generation_id}/performance-snapshots")
def add_performance_snapshot(generation_id: str, request: PerformanceSnapshotInput) -> dict:
    return PerformanceService(RepositoryService()).add_snapshot(
        generation_id,
        request.model_dump(exclude_none=True),
    )
