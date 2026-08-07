from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.backend.models.concepts import ConceptCreate, ConceptScoreRequest, ConceptUpdate
from app.backend.services.concept_service import ConceptService
from app.backend.services.repository_service import RepositoryService

router = APIRouter(prefix="/api/concepts", tags=["concepts"])
service = ConceptService(RepositoryService())


@router.get("")
def list_concepts(include_archived: Annotated[bool, Query()] = False) -> list[dict]:
    return service.list(include_archived)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_concept(payload: ConceptCreate) -> dict:
    record, backup = service.create(payload)
    return {"concept": record, "backup": backup}


@router.get("/{concept_id}")
def get_concept(concept_id: str) -> dict:
    return service.get(concept_id)


@router.put("/{concept_id}")
def update_concept(concept_id: str, payload: ConceptUpdate) -> dict:
    record, backup = service.update(concept_id, payload)
    return {"concept": record, "backup": backup}


@router.delete("/{concept_id}")
def delete_concept(concept_id: str, response: Response) -> dict:
    record, backups = service.delete(concept_id)
    response.status_code = status.HTTP_200_OK
    return {
        "concept": record,
        "backups": backups,
        "message": "Concept and its directional score records were deleted. Local backups were preserved.",
    }


@router.post("/{concept_id}/archive")
def archive_concept(concept_id: str) -> dict:
    record, backup = service.archive(concept_id)
    return {"concept": record, "backup": backup, "message": "Concept archived; no record was deleted."}


@router.post("/{concept_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_concept(concept_id: str) -> dict:
    record, backup = service.duplicate(concept_id)
    return {"concept": record, "backup": backup}


@router.post("/{concept_id}/score")
def score_concept(concept_id: str, request: ConceptScoreRequest) -> dict:
    score, backup = service.score(concept_id, request.save)
    return {"score": score, "backup": backup}
