from __future__ import annotations

from pathlib import Path

import pytest

from app.backend.models.sprites import SpriteSheetExportRequest
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.sprite_service import SpriteService
from app.backend.services.sprite_sheet_service import SpriteSheetService


def test_horizontal_sheet_generation_and_metadata(
    sprite_repository: RepositoryService,
    technical_frame_bytes: list[bytes],
) -> None:
    sprites = SpriteService(sprite_repository)
    sprites.upload_frames(
        "sprite-animation-dinko-blink",
        [(f"sample-{index}.png", content) for index, content in enumerate(technical_frame_bytes)],
    )
    sheets = SpriteSheetService(sprite_repository)
    record, _ = sheets.export(
        SpriteSheetExportRequest(
            animation_id="sprite-animation-dinko-blink",
            export_format="horizontal",
            padding=2,
        )
    )
    assert record["frame_count"] == 3
    assert record["sheet_width"] == 3 * (256 + 4)
    assert Path(sprite_repository.path(record["path"])).is_file()
    assert Path(sprite_repository.path(record["metadata_path"])).is_file()


def test_sprite_sheet_slicing_does_not_overwrite(
    sprite_repository: RepositoryService,
    technical_frame_bytes: list[bytes],
) -> None:
    sprites = SpriteService(sprite_repository)
    sprites.upload_frames(
        "sprite-animation-dinko-blink",
        [(f"sample-{index}.png", content) for index, content in enumerate(technical_frame_bytes)],
    )
    sheet_service = SpriteSheetService(sprite_repository)
    exported, _ = sheet_service.export(
        SpriteSheetExportRequest(animation_id="sprite-animation-dinko-blink", export_format="horizontal")
    )
    result = sheet_service.import_sheet(
        animation_id="sprite-animation-dinka-blink",
        filename="technical-sheet.png",
        content=sprite_repository.path(exported["path"]).read_bytes(),
        frame_width=260,
        frame_height=260,
        rows=1,
        columns=3,
        selected_cells=[0, 2],
    )
    assert len(result["frames"]) == 2


def test_sprite_sheet_import_rejects_empty_selection(
    sprite_repository: RepositoryService,
    technical_frame_bytes: list[bytes],
) -> None:
    sprites = SpriteService(sprite_repository)
    sprites.upload_frames("sprite-animation-dinko-blink", [("sample.png", technical_frame_bytes[0])])
    sheet_service = SpriteSheetService(sprite_repository)
    exported, _ = sheet_service.export(
        SpriteSheetExportRequest(animation_id="sprite-animation-dinko-blink", export_format="horizontal")
    )
    with pytest.raises(RepositoryError, match="Select at least one"):
        sheet_service.import_sheet(
            animation_id="sprite-animation-dinka-blink",
            filename="technical-sheet.png",
            content=sprite_repository.path(exported["path"]).read_bytes(),
            frame_width=260,
            frame_height=260,
            rows=1,
            columns=1,
            selected_cells=[],
        )
