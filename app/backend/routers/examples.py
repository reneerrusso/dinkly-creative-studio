from __future__ import annotations

from fastapi import APIRouter

from app.backend.services.markdown_service import MarkdownService
from app.backend.services.repository_service import RepositoryError, RepositoryService

router = APIRouter(prefix="/api/examples", tags=["examples"])
repository = RepositoryService()
markdown = MarkdownService(repository)


@router.get("")
def list_examples() -> list[dict]:
    return [item for item in markdown.markdown_files("EXAMPLES") if item["slug"] != "readme"]


@router.get("/{slug}")
def get_example(slug: str) -> dict:
    for item in list_examples():
        if item["slug"] == slug:
            return item
    raise RepositoryError("Example not found")

