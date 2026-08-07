from __future__ import annotations

from fastapi import APIRouter, status

from app.backend.models.sprites import SpriteCharacterCreate, SpriteCharacterUpdate, SpriteFrameUpdate
from app.backend.services.repository_service import RepositoryService
from app.backend.services.sprite_service import SpriteService

router = APIRouter(tags=["sprite studio"])
service = SpriteService(RepositoryService())


@router.get("/api/sprite-characters")
def list_characters() -> list[dict]:
    return service.list_characters()


@router.post("/api/sprite-characters", status_code=status.HTTP_201_CREATED)
def create_character(payload: SpriteCharacterCreate) -> dict:
    record, backup = service.create_character(payload)
    return {"character": record, "backup": backup}


@router.get("/api/sprite-characters/{character_id}")
def get_character(character_id: str) -> dict:
    return service.get_character(character_id)


@router.put("/api/sprite-characters/{character_id}")
def update_character(character_id: str, payload: SpriteCharacterUpdate) -> dict:
    record, backup = service.update_character(character_id, payload)
    return {"character": record, "backup": backup}


@router.put("/api/sprite-frames/{frame_id}")
def update_frame(frame_id: str, payload: SpriteFrameUpdate) -> dict:
    record, backup = service.update_frame(frame_id, payload)
    return {"frame": record, "backup": backup}


@router.delete("/api/sprite-frames/{frame_id}")
def delete_frame(frame_id: str) -> dict:
    record, backup = service.delete_frame(frame_id)
    return {"frame": record, "backup": backup}


@router.post("/api/sprite-frames/{frame_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_frame(frame_id: str) -> dict:
    record, backup = service.duplicate_frame(frame_id)
    return {"frame": record, "backup": backup}
