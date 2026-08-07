from __future__ import annotations

from fastapi import APIRouter

from app.backend.services.markdown_service import MarkdownService
from app.backend.services.repository_service import RepositoryError, RepositoryService

router = APIRouter(prefix="/api/prompt-templates", tags=["prompt templates"])
repository = RepositoryService()
markdown = MarkdownService(repository)


@router.get("")
def list_prompt_templates() -> list[dict]:
    return markdown.markdown_files("PROMPT_TEMPLATES")


@router.get("/{slug}")
def get_prompt_template(slug: str) -> dict:
    for item in list_prompt_templates():
        if item["slug"] == slug:
            return item
    raise RepositoryError("Prompt template not found")
