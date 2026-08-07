from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile, status

from app.backend.models.sprites import (
    FrameAlignRequest,
    FrameReorderRequest,
    SpriteAnimationCreate,
    SpriteAnimationUpdate,
)
from app.backend.services.repository_service import RepositoryService
from app.backend.services.sprite_service import SpriteService

router = APIRouter(prefix="/api/sprite-animations", tags=["sprite animations"])
service = SpriteService(RepositoryService())


@router.get("")
def list_animations(
    character_id: str | None = None,
    category: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    approved: bool | None = None,
    include_drafts: bool = True,
    q: str = "",
) -> list[dict]:
    return service.list_animations(
        character_id=character_id,
        category=category,
        status=status_filter,
        approved=approved,
        include_drafts=include_drafts,
        query=q,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_animation(payload: SpriteAnimationCreate) -> dict:
    record, backup = service.create_animation(payload)
    return {"animation": record, "backup": backup}


@router.get("/{animation_id}")
def get_animation(animation_id: str) -> dict:
    return service.get_animation(animation_id)


@router.put("/{animation_id}")
def update_animation(animation_id: str, payload: SpriteAnimationUpdate) -> dict:
    record, backup = service.update_animation(animation_id, payload)
    return {"animation": record, "backup": backup}


@router.delete("/{animation_id}")
def deprecate_animation(animation_id: str) -> dict:
    record, backup = service.deprecate_animation(animation_id)
    return {"animation": record, "backup": backup}


@router.post("/{animation_id}/frames", status_code=status.HTTP_201_CREATED)
async def upload_frames(
    animation_id: str,
    files: Annotated[list[UploadFile], File(description="Transparent PNG or WEBP frames")],
) -> dict:
    uploads = [(file.filename or "frame.png", await file.read()) for file in files]
    frames, backup = service.upload_frames(animation_id, uploads)
    return {"frames": frames, "backup": backup}


@router.post("/{animation_id}/reorder")
def reorder_frames(animation_id: str, payload: FrameReorderRequest) -> dict:
    frames, backup = service.reorder_frames(animation_id, payload)
    return {"frames": frames, "backup": backup}


@router.post("/{animation_id}/align")
def align_frames(animation_id: str, payload: FrameAlignRequest) -> dict:
    frames, backup = service.align_frames(animation_id, payload)
    return {"frames": frames, "backup": backup}


@router.post("/{animation_id}/validate")
def validate_animation(animation_id: str) -> dict:
    return service.validate_animation(animation_id)


@router.post("/{animation_id}/approve")
def approve_animation(animation_id: str) -> dict:
    record, backup = service.approve_animation(animation_id)
    return {"animation": record, "backup": backup}

