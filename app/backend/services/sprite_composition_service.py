from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.backend.models.sprites import (
    SharedInteractionCreate,
    SharedInteractionUpdate,
    SpriteCompositionCreate,
    SpriteCompositionUpdate,
)
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.sprite_service import SpriteService

COMPOSITIONS_PATH = "data/sprite_compositions.json"
INTERACTIONS_PATH = "app-data/sprites/shared_interactions.json"


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SpriteCompositionService:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository
        self.sprites = SpriteService(repository)

    def _compositions(self) -> list[dict[str, Any]]:
        records = self.repository.read_json(COMPOSITIONS_PATH, [])
        if not isinstance(records, list):
            raise RepositoryError(f"{COMPOSITIONS_PATH} must contain an array")
        return records

    def _save_compositions(self, records: list[dict[str, Any]]) -> str | None:
        return self.repository.write_json(
            COMPOSITIONS_PATH,
            records,
            schema_relative="schemas/sprite_composition.schema.json",
            validate_each=True,
        )

    def list(self) -> list[dict[str, Any]]:
        return sorted(self._compositions(), key=lambda item: str(item.get("updated_at", "")), reverse=True)

    def get(self, composition_id: str) -> dict[str, Any]:
        record = next((item for item in self._compositions() if item.get("id") == composition_id), None)
        if not record:
            raise RepositoryError("Sprite composition not found")
        return record

    def create(self, payload: SpriteCompositionCreate) -> tuple[dict[str, Any], str | None]:
        records = self._compositions()
        stamp = _now()
        record = {
            "id": f"sprite-composition-{uuid.uuid4().hex[:12]}",
            **payload.model_dump(),
            "status": "Draft",
            "created_at": stamp,
            "updated_at": stamp,
        }
        records.append(record)
        return record, self._save_compositions(records)

    def update(
        self,
        composition_id: str,
        payload: SpriteCompositionUpdate,
    ) -> tuple[dict[str, Any], str | None]:
        records = self._compositions()
        record = next((item for item in records if item.get("id") == composition_id), None)
        if not record:
            raise RepositoryError("Sprite composition not found")
        record.update(payload.model_dump(exclude_none=True))
        record["updated_at"] = _now()
        return record, self._save_compositions(records)

    def preview(self, composition_id: str) -> dict[str, Any]:
        composition = self.get(composition_id)
        animations = {item["id"]: item for item in self.sprites.list_animations(include_drafts=True)}
        resolved: list[dict[str, Any]] = []
        warnings: list[str] = []
        character_scales: dict[str, float] = {}
        for layer in sorted(composition["layers"], key=lambda item: int(item.get("z_index", 0))):
            animation_id = layer.get("animation_id")
            animation = animations.get(animation_id) if animation_id else None
            if animation_id and not animation:
                warnings.append(f"{layer['label']}: animation record is missing")
            elif animation and not animation.get("approved"):
                warnings.append(f"{layer['label']}: animation is not approved and will not appear in production selectors")
            if layer["layer_type"] in {"dinko", "dinka"}:
                character_scales[layer["layer_type"]] = float(layer.get("scale", 1))
            resolved.append({**layer, "animation": animation})
        if {"dinko", "dinka"}.issubset(character_scales) and abs(character_scales["dinko"] - character_scales["dinka"]) > 0.01:
            warnings.append("Dinko and Dinka use different scales; confirm this override is intentional")
        return {
            "composition": composition,
            "resolved_layers": resolved,
            "warnings": warnings,
            "renderable": not warnings and bool(resolved),
            "preview_type": "canvas-layer-plan",
        }

    def render_manifest(self, composition_id: str) -> dict[str, Any]:
        preview = self.preview(composition_id)
        composition = preview["composition"]
        target = self.repository.path(
            f"app-data/sprites/exports/{composition_id}-{uuid.uuid4().hex[:8]}.remotion.json"
        )
        manifest = {
            "type": "dinkly-sprite-composition",
            "composition": composition,
            "resolvedLayers": [
                {
                    "layer": {key: value for key, value in item.items() if key != "animation"},
                    "animation": item.get("animation"),
                }
                for item in preview["resolved_layers"]
            ],
            "warnings": preview["warnings"],
            "renderTarget": "Remotion MP4",
            "createdAt": _now(),
        }
        self.repository.atomic_write_bytes(target, (json.dumps(manifest, indent=2) + "\n").encode(), create_backup=False)
        blocked = bool(preview["warnings"])
        return {
            "status": "blocked" if blocked else "ready_for_remotion",
            "manifest_path": self.repository.relative(target),
            "manifest_url": f"/sprite-assets/{self.repository.relative(target).split('app-data/sprites/', 1)[1]}",
            "warnings": preview["warnings"],
            "message": (
                "Resolve the manifest warnings before production rendering."
                if blocked
                else "The composition manifest is ready. MP4 rendering starts when the optional Remotion runtime is installed."
            ),
        }

    def _interactions(self) -> list[dict[str, Any]]:
        records = self.repository.read_json(INTERACTIONS_PATH, [])
        if not isinstance(records, list):
            raise RepositoryError(f"{INTERACTIONS_PATH} must contain an array")
        return records

    def _save_interactions(self, records: list[dict[str, Any]]) -> str | None:
        return self.repository.write_json(INTERACTIONS_PATH, records)

    def list_interactions(self) -> list[dict[str, Any]]:
        return self._interactions()

    def create_interaction(self, payload: SharedInteractionCreate) -> tuple[dict[str, Any], str | None]:
        self._validate_interaction(payload.model_dump())
        stamp = _now()
        record = {
            "id": f"shared-interaction-{uuid.uuid4().hex[:12]}",
            **payload.model_dump(),
            "created_at": stamp,
            "updated_at": stamp,
        }
        records = self._interactions()
        records.append(record)
        return record, self._save_interactions(records)

    def update_interaction(
        self,
        interaction_id: str,
        payload: SharedInteractionUpdate,
    ) -> tuple[dict[str, Any], str | None]:
        records = self._interactions()
        record = next((item for item in records if item.get("id") == interaction_id), None)
        if not record:
            raise RepositoryError("Shared interaction not found")
        candidate = {**record, **payload.model_dump(exclude_none=True)}
        self._validate_interaction(candidate)
        record.update(candidate)
        record["updated_at"] = _now()
        return record, self._save_interactions(records)

    def _validate_interaction(self, record: dict[str, Any]) -> None:
        dinko = self.sprites.get_animation(str(record["dinko_animation_id"]))
        dinka = self.sprites.get_animation(str(record["dinka_animation_id"]))
        if (dinko.get("character") or {}).get("character_type") != "dinko":
            raise RepositoryError("dinko_animation_id must reference a Dinko animation")
        if (dinka.get("character") or {}).get("character_type") != "dinka":
            raise RepositoryError("dinka_animation_id must reference a Dinka animation")
        if record.get("approved") and (not dinko.get("approved") or not dinka.get("approved")):
            raise RepositoryError("A shared interaction can be approved only when both animations are approved")
        for key in ("dinko_offset", "dinka_offset"):
            offset = record.get(key) or {}
            if not all(axis in offset for axis in ("x", "y")):
                raise RepositoryError(f"{key} must contain normalized x and y values")
            if any(abs(float(offset[axis])) > 2 for axis in ("x", "y")):
                raise RepositoryError(f"{key} values must stay within the coordinated canvas")
