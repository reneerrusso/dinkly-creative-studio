from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from app.backend.models.sprites import (
    FrameAlignRequest,
    FrameReorderRequest,
    SpriteAnimationCreate,
    SpriteAnimationUpdate,
    SpriteCharacterCreate,
    SpriteCharacterUpdate,
    SpriteFrameUpdate,
)
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.sprite_validation_service import SpriteValidationService

CHARACTERS_PATH = "data/sprite_characters.json"
ANIMATIONS_PATH = "data/sprite_animations.json"
FRAMES_PATH = "app-data/sprites/frames.json"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "animation"


class SpriteService:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository
        self.validation = SpriteValidationService(repository)

    def _characters(self) -> list[dict[str, Any]]:
        records = self.repository.read_json(CHARACTERS_PATH, [])
        if not isinstance(records, list):
            raise RepositoryError(f"{CHARACTERS_PATH} must contain an array")
        return records

    def _animations(self) -> list[dict[str, Any]]:
        records = self.repository.read_json(ANIMATIONS_PATH, [])
        if not isinstance(records, list):
            raise RepositoryError(f"{ANIMATIONS_PATH} must contain an array")
        return records

    def _frames(self) -> list[dict[str, Any]]:
        records = self.repository.read_json(FRAMES_PATH, [])
        if not isinstance(records, list):
            raise RepositoryError(f"{FRAMES_PATH} must contain an array")
        return records

    def _save_characters(self, records: list[dict[str, Any]]) -> str | None:
        return self.repository.write_json(
            CHARACTERS_PATH,
            records,
            schema_relative="schemas/sprite_character.schema.json",
            validate_each=True,
        )

    def _save_animations(self, records: list[dict[str, Any]]) -> str | None:
        return self.repository.write_json(
            ANIMATIONS_PATH,
            records,
            schema_relative="schemas/sprite_animation.schema.json",
            validate_each=True,
        )

    def _save_frames(self, records: list[dict[str, Any]]) -> str | None:
        return self.repository.write_json(
            FRAMES_PATH,
            records,
            schema_relative="schemas/sprite_frame.schema.json",
            validate_each=True,
        )

    def list_characters(self) -> list[dict[str, Any]]:
        animations = self._animations()
        return [
            {
                **character,
                "animation_count": sum(1 for item in animations if item.get("character_id") == character.get("id")),
                "reference_status": "Locked official reference" if character.get("locked") else "Managed asset group",
            }
            for character in self._characters()
        ]

    def get_character(self, character_id: str) -> dict[str, Any]:
        character = next((item for item in self.list_characters() if item.get("id") == character_id), None)
        if not character:
            raise RepositoryError("Sprite character not found")
        character["animations"] = self.list_animations(character_id=character_id, include_drafts=True)
        return character

    def create_character(self, payload: SpriteCharacterCreate) -> tuple[dict[str, Any], str | None]:
        records = self._characters()
        if any(item.get("slug") == payload.slug for item in records):
            raise RepositoryError(f"Duplicate sprite character slug: {payload.slug}")
        stamp = _now()
        record = {
            "id": f"sprite-character-{uuid.uuid4().hex[:12]}",
            **payload.model_dump(),
            "locked": False,
            "created_at": stamp,
            "updated_at": stamp,
        }
        records.append(record)
        return record, self._save_characters(records)

    def update_character(self, character_id: str, payload: SpriteCharacterUpdate) -> tuple[dict[str, Any], str | None]:
        records = self._characters()
        record = next((item for item in records if item.get("id") == character_id), None)
        if not record:
            raise RepositoryError("Sprite character not found")
        changes = payload.model_dump(exclude_none=True)
        if record.get("locked") and "approved" in changes and not changes["approved"]:
            raise RepositoryError("Locked official characters cannot be unapproved")
        record.update(changes)
        record["updated_at"] = _now()
        return record, self._save_characters(records)

    def list_animations(
        self,
        *,
        character_id: str | None = None,
        category: str | None = None,
        status: str | None = None,
        approved: bool | None = None,
        include_drafts: bool = True,
        query: str = "",
    ) -> list[dict[str, Any]]:
        frames = self._frames()
        characters = {item["id"]: item for item in self._characters()}
        results: list[dict[str, Any]] = []
        for animation in self._animations():
            animation_frames = sorted(
                (frame for frame in frames if frame.get("animation_id") == animation.get("id")),
                key=lambda frame: int(frame.get("frame_index", 0)),
            )
            enriched = self._enrich_animation(animation, animation_frames, characters.get(str(animation.get("character_id"))))
            if character_id and enriched.get("character_id") != character_id:
                continue
            if category and enriched.get("category") != category:
                continue
            if status and enriched.get("status") != status:
                continue
            if approved is not None and bool(enriched.get("approved")) != approved:
                continue
            if not include_drafts and not enriched.get("approved"):
                continue
            if query and query.lower() not in f"{enriched.get('name')} {' '.join(enriched.get('tags', []))}".lower():
                continue
            results.append(enriched)
        return results

    def _enrich_animation(
        self,
        animation: dict[str, Any],
        frames: list[dict[str, Any]],
        character: dict[str, Any] | None,
    ) -> dict[str, Any]:
        frame_count = len(frames)
        duration = sum(int(frame.get("duration_ms", 0)) for frame in frames)
        if animation.get("approval_level") == "Deprecated":
            status = "Draft"
        elif animation.get("approved"):
            status = "Exported" if animation.get("status") == "Exported" else "Approved"
        elif not frame_count:
            status = "Frames needed"
        elif any(frame.get("validation_status") == "invalid" for frame in frames):
            status = "Needs review"
        else:
            status = "Draft"
        return {
            **animation,
            "frame_ids": [frame["id"] for frame in frames],
            "frames": [self._with_asset_url(frame) for frame in frames],
            "frame_count": frame_count,
            "duration_ms": duration,
            "status": status,
            "character": character,
        }

    def get_animation(self, animation_id: str) -> dict[str, Any]:
        animation = next((item for item in self.list_animations(include_drafts=True) if item.get("id") == animation_id), None)
        if not animation:
            raise RepositoryError("Sprite animation not found")
        animation["validation_checklist"] = self.validation.checklist(
            str((animation.get("character") or {}).get("character_type", "shared"))
        )
        return animation

    def create_animation(self, payload: SpriteAnimationCreate) -> tuple[dict[str, Any], str | None]:
        self.get_character(payload.character_id)
        records = self._animations()
        slug = payload.slug or _slug(payload.name)
        character_slug = next(item["slug"] for item in self._characters() if item["id"] == payload.character_id)
        if not slug.startswith(f"{character_slug}-"):
            slug = f"{character_slug}-{slug}"
        if any(item.get("slug") == slug for item in records):
            raise RepositoryError(f"Duplicate sprite animation slug: {slug}")
        stamp = _now()
        record = {
            "id": f"sprite-animation-{uuid.uuid4().hex[:12]}",
            **payload.model_dump(exclude={"slug"}),
            "slug": slug,
            "frame_ids": [],
            "approved": False,
            "approval_level": "Draft",
            "thumbnail_path": None,
            "preview_path": None,
            "status": "Frames needed",
            "validation_status": "Frames needed",
            "created_at": stamp,
            "updated_at": stamp,
        }
        records.append(record)
        backup = self._save_animations(records)
        return self.get_animation(record["id"]), backup

    def update_animation(self, animation_id: str, payload: SpriteAnimationUpdate) -> tuple[dict[str, Any], str | None]:
        records = self._animations()
        record = next((item for item in records if item.get("id") == animation_id), None)
        if not record:
            raise RepositoryError("Sprite animation not found")
        record.update(payload.model_dump(exclude_none=True))
        loop_start = int(record.get("loop_start_frame", 0))
        loop_end = record.get("loop_end_frame")
        if loop_end is not None and int(loop_end) < loop_start:
            raise RepositoryError("Loop end must be at or after loop start")
        record["approved"] = record.get("approval_level") == "Approved"
        record["updated_at"] = _now()
        backup = self._save_animations(records)
        return self.get_animation(animation_id), backup

    def deprecate_animation(self, animation_id: str) -> tuple[dict[str, Any], str | None]:
        return self.update_animation(animation_id, SpriteAnimationUpdate(approval_level="Deprecated"))

    def upload_frames(
        self,
        animation_id: str,
        uploads: list[tuple[str, bytes]],
    ) -> tuple[list[dict[str, Any]], str | None]:
        animation = self.get_animation(animation_id)
        character = animation["character"]
        character_type = str(character.get("character_type"))
        records = self._frames()
        existing_hashes = {str(frame.get("sha256")) for frame in records if frame.get("sha256")}
        expected = None
        animation_frames = animation.get("frames", [])
        if animation_frames:
            expected = (int(animation_frames[0]["width"]), int(animation_frames[0]["height"]))
        else:
            expected = (int(character["default_canvas_width"]), int(character["default_canvas_height"]))
        directory_name = character_type if character_type in {"dinko", "dinka"} else f"{character_type}s"
        target_dir = self.repository.path(f"app-data/sprites/characters/{directory_name}/{animation['slug']}")
        if character_type == "shared":
            target_dir = self.repository.path(f"app-data/sprites/shared/{animation['slug']}")
        elif character_type == "prop":
            target_dir = self.repository.path(f"app-data/sprites/props/{animation['slug']}")
        elif character_type == "effect":
            target_dir = self.repository.path(f"app-data/sprites/effects/{animation['slug']}")
        target_dir.mkdir(parents=True, exist_ok=True)
        added: list[dict[str, Any]] = []
        for original_name, content in uploads:
            upload = self.validation.validate_upload(
                filename=original_name,
                content=content,
                character_type=character_type,
                expected_dimensions=expected,
            )
            digest = hashlib.sha256(content).hexdigest()
            if digest in existing_hashes:
                raise RepositoryError(f"Duplicate sprite frame upload: {original_name}")
            filename = f"frame-{len(animation_frames) + len(added) + 1:04d}-{uuid.uuid4().hex[:8]}{upload['extension']}"
            target = target_dir / filename
            self.repository.atomic_write_bytes(target, content, create_backup=False)
            inspection = self.validation.inspect(target)
            warnings = self.validation.image_warnings(
                inspection,
                character_type=character_type,
                expected_dimensions=expected,
            )
            stamp = _now()
            frame = {
                "id": f"sprite-frame-{uuid.uuid4().hex[:12]}",
                "character_id": animation["character_id"],
                "animation_id": animation_id,
                "frame_index": len(animation_frames) + len(added),
                "image_path": self.repository.relative(target),
                "width": int(inspection["width"]),
                "height": int(inspection["height"]),
                "duration_ms": round(1000 / float(animation["frame_rate"])),
                "anchor_x": float(animation.get("default_anchor_x", 0.5)),
                "anchor_y": float(animation.get("default_anchor_y", 1)),
                "offset_x": 0,
                "offset_y": 0,
                "opacity": 1,
                "approved": False,
                "validation_status": "warning" if warnings else "valid",
                "validation_warnings": warnings,
                "review_status": "Not reviewed",
                "review_notes": "",
                "sha256": digest,
                "transparent": bool(inspection.get("transparent")),
                "created_at": stamp,
                "updated_at": stamp,
            }
            added.append(frame)
            existing_hashes.add(digest)
        records.extend(added)
        backup = self._save_frames(records)
        self._refresh_animation_assets(animation_id)
        return [self._with_asset_url(frame) for frame in added], backup

    def _refresh_animation_assets(self, animation_id: str) -> None:
        animation = self.get_animation(animation_id)
        frames = animation.get("frames", [])
        records = self._animations()
        record = next(item for item in records if item.get("id") == animation_id)
        record["frame_ids"] = [frame["id"] for frame in frames]
        record["status"] = "Draft" if frames else "Frames needed"
        if frames and not record.get("thumbnail_path"):
            target = self.repository.path(f"app-data/sprites/thumbnails/{animation_id}-{uuid.uuid4().hex[:8]}.png")
            self.validation.run_worker(
                "thumbnail",
                {"path": str(self.repository.path(frames[0]["image_path"])), "output": str(target)},
            )
            record["thumbnail_path"] = self.repository.relative(target)
        record["updated_at"] = _now()
        self._save_animations(records)

    def update_frame(self, frame_id: str, payload: SpriteFrameUpdate) -> tuple[dict[str, Any], str | None]:
        records = self._frames()
        record = next((item for item in records if item.get("id") == frame_id), None)
        if not record:
            raise RepositoryError("Sprite frame not found")
        record.update(payload.model_dump(exclude_none=True))
        if record.get("review_status") != "Pass":
            record["approved"] = False
        record["updated_at"] = _now()
        backup = self._save_frames(records)
        return self._with_asset_url(record), backup

    def delete_frame(self, frame_id: str) -> tuple[dict[str, Any], str | None]:
        records = self._frames()
        record = next((item for item in records if item.get("id") == frame_id), None)
        if not record:
            raise RepositoryError("Sprite frame not found")
        records = [item for item in records if item.get("id") != frame_id]
        for index, item in enumerate(sorted((item for item in records if item.get("animation_id") == record["animation_id"]), key=lambda value: value["frame_index"])):
            item["frame_index"] = index
        backup = self._save_frames(records)
        self._refresh_animation_assets(str(record["animation_id"]))
        return record, backup

    def duplicate_frame(self, frame_id: str) -> tuple[dict[str, Any], str | None]:
        records = self._frames()
        source = next((item for item in records if item.get("id") == frame_id), None)
        if not source:
            raise RepositoryError("Sprite frame not found")
        siblings = [item for item in records if item.get("animation_id") == source["animation_id"]]
        insert_at = int(source["frame_index"]) + 1
        for frame in siblings:
            if int(frame["frame_index"]) >= insert_at:
                frame["frame_index"] = int(frame["frame_index"]) + 1
        stamp = _now()
        duplicate = {
            **source,
            "id": f"sprite-frame-{uuid.uuid4().hex[:12]}",
            "frame_index": insert_at,
            "approved": False,
            "review_status": "Not reviewed",
            "review_notes": "Duplicated from an existing frame for timing; artwork file is shared.",
            "created_at": stamp,
            "updated_at": stamp,
        }
        records.append(duplicate)
        backup = self._save_frames(records)
        self._refresh_animation_assets(str(source["animation_id"]))
        return self._with_asset_url(duplicate), backup

    def reorder_frames(self, animation_id: str, payload: FrameReorderRequest) -> tuple[list[dict[str, Any]], str | None]:
        self.get_animation(animation_id)
        records = self._frames()
        current = [item for item in records if item.get("animation_id") == animation_id]
        current_ids = {str(item["id"]) for item in current}
        if set(payload.frame_ids) != current_ids:
            raise RepositoryError("Reorder must contain every frame exactly once")
        order = {frame_id: index for index, frame_id in enumerate(payload.frame_ids)}
        for frame in current:
            frame["frame_index"] = order[str(frame["id"])]
            frame["updated_at"] = _now()
        backup = self._save_frames(records)
        return [self._with_asset_url(frame) for frame in sorted(current, key=lambda item: item["frame_index"])], backup

    def align_frames(self, animation_id: str, payload: FrameAlignRequest) -> tuple[list[dict[str, Any]], str | None]:
        animation = self.get_animation(animation_id)
        frames = self._frames()
        current = [item for item in frames if item.get("animation_id") == animation_id]
        if not current:
            raise RepositoryError("Upload frames before aligning this animation")
        if payload.mode == "selected_frame":
            selected = next((item for item in current if item.get("id") == payload.selected_frame_id), None)
            if not selected:
                raise RepositoryError("Selected alignment frame is not part of this animation")
            target = (selected["anchor_x"], selected["anchor_y"], selected["offset_x"], selected["offset_y"])
        else:
            target = (
                float(animation.get("default_anchor_x", 0.5)),
                float(animation.get("default_anchor_y", 1)),
                0,
                0,
            )
        for frame in current:
            frame["anchor_x"], frame["anchor_y"], frame["offset_x"], frame["offset_y"] = target
            frame["updated_at"] = _now()
        backup = self._save_frames(frames)
        return [self._with_asset_url(frame) for frame in sorted(current, key=lambda item: item["frame_index"])], backup

    def validate_animation(self, animation_id: str) -> dict[str, Any]:
        animation = self.get_animation(animation_id)
        issues = self.validation.animation_warnings(animation.get("frames", []))
        blocking = any(issue["severity"] == "error" for issue in issues)
        records = self._animations()
        record = next(item for item in records if item.get("id") == animation_id)
        record["validation_status"] = "Invalid" if blocking else "Needs review" if issues else "Ready for review"
        record["updated_at"] = _now()
        self._save_animations(records)
        return {
            "animation_id": animation_id,
            "status": record["validation_status"],
            "issues": issues,
            "checklist": animation["validation_checklist"],
            "blocking": blocking,
        }

    def approve_animation(self, animation_id: str) -> tuple[dict[str, Any], str | None]:
        animation = self.get_animation(animation_id)
        frames = animation.get("frames", [])
        if animation.get("technical_sample"):
            raise RepositoryError("Technical sample animations can never be approved as official assets")
        if not frames:
            raise RepositoryError("Upload and review frames before approving an animation")
        validation = self.validate_animation(animation_id)
        if validation["blocking"]:
            raise RepositoryError("Resolve blocking frame validation issues before approval")
        if any(frame.get("review_status") != "Pass" for frame in frames):
            raise RepositoryError("Every frame must pass manual frame review before animation approval")
        records = self._animations()
        record = next(item for item in records if item.get("id") == animation_id)
        record.update({"approved": True, "approval_level": "Approved", "status": "Approved", "updated_at": _now()})
        backup = self._save_animations(records)
        return self.get_animation(animation_id), backup

    def _with_asset_url(self, frame: dict[str, Any]) -> dict[str, Any]:
        relative = str(frame.get("image_path", ""))
        marker = "app-data/sprites/"
        asset_url = f"/sprite-assets/{relative.split(marker, 1)[1]}" if marker in relative else ""
        return {**frame, "asset_url": asset_url}
