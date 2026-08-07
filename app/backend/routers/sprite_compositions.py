from __future__ import annotations

from fastapi import APIRouter, status

from app.backend.models.sprites import (
    SharedInteractionCreate,
    SharedInteractionUpdate,
    SpriteCompositionCreate,
    SpriteCompositionUpdate,
)
from app.backend.services.repository_service import RepositoryService
from app.backend.services.sprite_composition_service import SpriteCompositionService

router = APIRouter(tags=["sprite compositions"])
service = SpriteCompositionService(RepositoryService())


@router.get("/api/sprite-compositions")
def list_compositions() -> list[dict]:
    return service.list()


@router.post("/api/sprite-compositions", status_code=status.HTTP_201_CREATED)
def create_composition(payload: SpriteCompositionCreate) -> dict:
    record, backup = service.create(payload)
    return {"composition": record, "backup": backup}


@router.get("/api/sprite-compositions/{composition_id}")
def get_composition(composition_id: str) -> dict:
    return service.get(composition_id)


@router.put("/api/sprite-compositions/{composition_id}")
def update_composition(composition_id: str, payload: SpriteCompositionUpdate) -> dict:
    record, backup = service.update(composition_id, payload)
    return {"composition": record, "backup": backup}


@router.post("/api/sprite-compositions/{composition_id}/preview")
def preview_composition(composition_id: str) -> dict:
    return service.preview(composition_id)


@router.post("/api/sprite-compositions/{composition_id}/render")
def render_composition(composition_id: str) -> dict:
    return service.render_manifest(composition_id)


@router.get("/api/shared-interactions")
def list_shared_interactions() -> list[dict]:
    return service.list_interactions()


@router.post("/api/shared-interactions", status_code=status.HTTP_201_CREATED)
def create_shared_interaction(payload: SharedInteractionCreate) -> dict:
    record, backup = service.create_interaction(payload)
    return {"interaction": record, "backup": backup}


@router.put("/api/shared-interactions/{interaction_id}")
def update_shared_interaction(interaction_id: str, payload: SharedInteractionUpdate) -> dict:
    record, backup = service.update_interaction(interaction_id, payload)
    return {"interaction": record, "backup": backup}

