from __future__ import annotations

from fastapi import APIRouter, status

from app.backend.models.reviews import ArtReviewInput, EditPromptRequest
from app.backend.services.art_review_service import ArtReviewService
from app.backend.services.repository_service import RepositoryService

router = APIRouter(prefix="/api/art-reviews", tags=["art reviews"])
service = ArtReviewService(RepositoryService())


@router.get("")
def list_reviews() -> list[dict]:
    return service.list()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_review(payload: ArtReviewInput) -> dict:
    record, backup = service.create(payload)
    return {"review": record, "backup": backup}


@router.post("/edit-prompt")
def create_edit_prompt(payload: EditPromptRequest) -> dict:
    return service.edit_prompt(payload)

