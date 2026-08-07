from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status

from app.backend.models.sprites import SpriteSheetExportRequest
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.sprite_export_service import SpriteExportService
from app.backend.services.sprite_sheet_service import SpriteSheetService

router = APIRouter(tags=["sprite exports"])
repository = RepositoryService()
sheet_service = SpriteSheetService(repository)
export_service = SpriteExportService(repository)


@router.post("/api/sprite-sheets/import", status_code=status.HTTP_201_CREATED)
async def import_sprite_sheet(
    file: Annotated[UploadFile, File()],
    animation_id: Annotated[str, Form()],
    frame_width: Annotated[int, Form()],
    frame_height: Annotated[int, Form()],
    row_count: Annotated[int, Form()],
    column_count: Annotated[int, Form()],
    selected_cells: Annotated[str | None, Form()] = None,
    transparent_background: Annotated[bool, Form()] = True,
) -> dict:
    cells = json.loads(selected_cells) if selected_cells else None
    if cells is not None and not isinstance(cells, list):
        raise RepositoryError("selected_cells must be a JSON array")
    return sheet_service.import_sheet(
        animation_id=animation_id,
        filename=file.filename or "sprite-sheet.png",
        content=await file.read(),
        frame_width=frame_width,
        frame_height=frame_height,
        rows=row_count,
        columns=column_count,
        selected_cells=cells,
        transparent_background=transparent_background,
    )


@router.post("/api/sprite-sheets/export", status_code=status.HTTP_201_CREATED)
def export_sprite_sheet(payload: SpriteSheetExportRequest) -> dict:
    record, backup = export_service.export(payload)
    return {"export": record, "backup": backup}


@router.get("/api/sprite-exports")
def list_sprite_exports() -> list[dict]:
    return export_service.list()
