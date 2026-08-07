from __future__ import annotations

from fastapi import APIRouter

from app.backend.models.prompts import BrandIntegrationRequest
from app.backend.services.concept_service import ConceptService
from app.backend.services.prompt_service import PromptService
from app.backend.services.repository_service import RepositoryService

router = APIRouter(prefix="/api/brand-integrations", tags=["brand integrations"])
repository = RepositoryService()
service = PromptService(repository, ConceptService(repository))


@router.post("/generate")
def generate(payload: BrandIntegrationRequest) -> dict:
    return service.generate_brand_integration(payload)

