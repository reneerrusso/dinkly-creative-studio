from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.backend.services.repository_service import RepositoryService

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
repository = RepositoryService()


class KnowledgeUpdate(BaseModel):
    content: str = Field(min_length=80)


@router.get("")
def list_documents() -> list[dict]:
    return [
        {key: value for key, value in document.items() if key != "content"}
        for document in repository.list_documents()
    ]


@router.get("/{document}")
def get_document(document: str) -> dict:
    return repository.read_markdown(document)


@router.put("/{document}")
def update_document(document: str, payload: KnowledgeUpdate) -> dict:
    return repository.write_markdown(document, payload.content)

