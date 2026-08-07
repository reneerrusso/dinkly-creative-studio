from __future__ import annotations

import json

from app.backend.models.sprites import (
    SharedInteractionCreate,
    SpriteCompositionCreate,
    SpriteSheetExportRequest,
)
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.sprite_composition_service import SpriteCompositionService
from app.backend.services.sprite_export_service import SpriteExportService
from app.backend.services.sprite_service import SpriteService


def test_generic_metadata_export(sprite_repository: RepositoryService, technical_frame_bytes: list[bytes]) -> None:
    SpriteService(sprite_repository).upload_frames(
        "sprite-animation-dinko-blink",
        [(f"frame-{index}.png", content) for index, content in enumerate(technical_frame_bytes)],
    )
    record, _ = SpriteExportService(sprite_repository).export(
        SpriteSheetExportRequest(
            animation_id="sprite-animation-dinko-blink",
            export_format="metadata_json",
        )
    )
    payload = json.loads(sprite_repository.path(record["path"]).read_text(encoding="utf-8"))
    assert payload["name"] == "dinko-blink"
    assert payload["anchor"] == {"x": 0.5, "y": 1.0}
    assert len(payload["frames"]) == 3


def test_shared_interaction_requires_correct_characters(sprite_repository: RepositoryService) -> None:
    service = SpriteCompositionService(sprite_repository)
    record, _ = service.create_interaction(
        SharedInteractionCreate(
            name="Shared Hug",
            dinko_animation_id="sprite-animation-dinko-hug",
            dinka_animation_id="sprite-animation-dinka-hug",
        )
    )
    assert record["approved"] is False
    try:
        service.create_interaction(
            SharedInteractionCreate(
                name="Wrong pair",
                dinko_animation_id="sprite-animation-dinka-hug",
                dinka_animation_id="sprite-animation-dinko-hug",
            )
        )
    except RepositoryError:
        pass
    else:
        raise AssertionError("invalid coordinated characters were accepted")


def test_composition_preview_warns_for_unapproved_layers(sprite_repository: RepositoryService) -> None:
    service = SpriteCompositionService(sprite_repository)
    composition, _ = service.create(
        SpriteCompositionCreate(
            name="Blink test",
            layers=[
                {
                    "id": "dinko-layer",
                    "layer_type": "dinko",
                    "animation_id": "sprite-animation-dinko-blink",
                    "label": "Dinko blink",
                }
            ],
        )
    )
    preview = service.preview(composition["id"])
    assert preview["warnings"]
    assert preview["preview_type"] == "canvas-layer-plan"
    handoff = service.render_manifest(composition["id"])
    assert handoff["status"] == "blocked"
    assert "Resolve" in handoff["message"]
