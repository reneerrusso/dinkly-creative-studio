from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status

from app.backend.models.prompts import PromptGenerateRequest, PromptSaveRequest
from app.backend.services.concept_service import ConceptService
from app.backend.services.prompt_service import PromptService
from app.backend.services.reference_analysis_service import ReferenceAnalysisService
from app.backend.services.repository_service import RepositoryError, RepositoryService

router = APIRouter(prefix="/api/prompts", tags=["prompts"])
repository = RepositoryService()
service = PromptService(repository, ConceptService(repository))
reference_analysis = ReferenceAnalysisService(repository)


@router.get("")
def list_prompts() -> list[dict]:
    return service.list()


@router.post("/reference-image")
async def upload_scene_reference(file: Annotated[UploadFile, File()]) -> dict:
    content = await file.read()
    record = repository.save_upload(file.filename or "scene-reference.png", content)
    try:
        analysis = reference_analysis.analyze(record["path"])
        return {**record, **analysis, "analysis_error": None}
    except RepositoryError as exc:
        # Keep the upload available so the user can supply or correct the
        # written description instead of losing their work.
        return {**record, "signals": {}, "scene_brief": "", "analysis_error": str(exc)}


@router.post("/generate")
def generate_prompt(payload: PromptGenerateRequest) -> dict:
    return service.generate(payload)


@router.post("", status_code=status.HTTP_201_CREATED)
def save_prompt(payload: PromptSaveRequest) -> dict:
    record, backup = service.save(payload)
    return {"prompt": record, "backup": backup}


@router.put("/{prompt_id}")
def update_prompt(prompt_id: str, payload: PromptSaveRequest) -> dict:
    record, backup = service.update(prompt_id, payload)
    return {"prompt": record, "backup": backup}
