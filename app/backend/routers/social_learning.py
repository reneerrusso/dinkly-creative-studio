from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status

from app.backend.models.social_posts import SocialPostInput
from app.backend.services.repository_service import RepositoryService
from app.backend.services.social_learning_service import SocialLearningService

router = APIRouter(prefix="/api", tags=["social learning"])
repository = RepositoryService()
service = SocialLearningService(repository)


@router.get("/social-posts")
def list_posts() -> list[dict]:
    return service.posts()


@router.post("/social-posts", status_code=status.HTTP_201_CREATED)
def create_post(payload: SocialPostInput) -> dict:
    record, backup = service.create_post(payload)
    return {"post": record, "backup": backup}


@router.post("/social-posts/upload", status_code=status.HTTP_201_CREATED)
async def upload_post_image(file: Annotated[UploadFile, File()]) -> dict:
    content = await file.read()
    return repository.save_upload(file.filename or "comic.png", content)


@router.get("/social-posts/{post_id}")
def get_post(post_id: str) -> dict:
    return service.get_post(post_id)


@router.post("/social-learning/analyze")
def analyze() -> dict:
    return service.analyze()


@router.get("/social-learnings")
def list_learnings() -> list[dict]:
    return service.learnings()


@router.get("/social-patterns")
def patterns() -> dict:
    return service.patterns()


@router.get("/social-reports")
def reports() -> list[dict]:
    return service.reports()
