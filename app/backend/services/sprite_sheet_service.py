from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.backend.models.sprites import SpriteSheetExportRequest
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.sprite_service import SpriteService

SHEETS_PATH = "data/sprite_sheets.json"


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SpriteSheetService:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository
        self.sprites = SpriteService(repository)
        self.validation = self.sprites.validation

    def list_exports(self) -> list[dict[str, Any]]:
        records = self.repository.read_json(SHEETS_PATH, [])
        if not isinstance(records, list):
            raise RepositoryError(f"{SHEETS_PATH} must contain an array")
        return sorted(records, key=lambda item: str(item.get("created_at", "")), reverse=True)

    def import_sheet(
        self,
        *,
        animation_id: str,
        filename: str,
        content: bytes,
        frame_width: int,
        frame_height: int,
        rows: int,
        columns: int,
        selected_cells: list[int] | None,
        transparent_background: bool = True,
    ) -> dict[str, Any]:
        if Path(filename).suffix.lower() not in {".png", ".webp"}:
            raise RepositoryError("Sprite sheet imports must be PNG or WEBP")
        if not content or len(content) > self.repository.settings.max_upload_bytes:
            raise RepositoryError("Sprite sheet is empty or exceeds the configured upload limit")
        if min(frame_width, frame_height, rows, columns) < 1:
            raise RepositoryError("Frame dimensions, rows, and columns must be positive")
        self.sprites.get_animation(animation_id)
        with tempfile.TemporaryDirectory(prefix="dinkly-sprite-import-") as temporary:
            source = Path(temporary) / f"sheet{Path(filename).suffix.lower()}"
            source.write_bytes(content)
            result = self.validation.run_worker(
                "slice",
                {
                    "path": str(source),
                    "output_dir": str(Path(temporary) / "frames"),
                    "frame_width": frame_width,
                    "frame_height": frame_height,
                    "rows": rows,
                    "columns": columns,
                    "selected_cells": selected_cells,
                },
            )
            if transparent_background:
                for path in result["paths"]:
                    if not self.validation.run_worker("inspect", {"path": path}).get("transparent"):
                        raise RepositoryError("The selected cells must have a transparent background")
            uploads = [(Path(path).name, Path(path).read_bytes()) for path in result["paths"]]
            frames, backup = self.sprites.upload_frames(animation_id, uploads)
        return {
            "animation_id": animation_id,
            "frames": frames,
            "backup": backup,
            "source_name": filename,
            "transparent_background": transparent_background,
        }

    def export(self, payload: SpriteSheetExportRequest) -> tuple[dict[str, Any], str | None]:
        animation = self.sprites.get_animation(payload.animation_id)
        frames = animation.get("frames", [])
        if not frames:
            raise RepositoryError("Upload frames before exporting an animation")
        if animation.get("approval_level") == "Deprecated":
            raise RepositoryError("Deprecated animations cannot be exported")
        export_id = f"sprite-export-{uuid.uuid4().hex[:12]}"
        export_dir = self.repository.path(f"app-data/sprites/exports/{export_id}")
        export_dir.mkdir(parents=True, exist_ok=False)
        frame_paths = [str(self.repository.path(frame["image_path"])) for frame in frames]
        durations = [int(frame["duration_ms"]) for frame in frames]
        file_result: dict[str, Any]
        if payload.export_format in {"horizontal", "vertical", "grid"}:
            target = export_dir / f"{animation['slug']}-{payload.export_format}.png"
            file_result = self.validation.run_worker(
                "sheet",
                {
                    "frame_paths": frame_paths,
                    "output": str(target),
                    "layout": payload.export_format,
                    "padding": payload.padding,
                    "columns": payload.columns,
                    "power_of_two": payload.power_of_two,
                },
            )
        elif payload.export_format in {"gif", "webp"}:
            target = export_dir / f"{animation['slug']}.{payload.export_format}"
            file_result = self.validation.run_worker(
                "animation",
                {
                    "frame_paths": frame_paths,
                    "durations": durations,
                    "output": str(target),
                    "format": payload.export_format,
                    "loop": bool(animation.get("loop")),
                },
            )
            file_result.update(
                {
                    "frame_width": max(int(frame["width"]) for frame in frames),
                    "frame_height": max(int(frame["height"]) for frame in frames),
                    "sheet_width": max(int(frame["width"]) for frame in frames),
                    "sheet_height": max(int(frame["height"]) for frame in frames),
                    "cells": [],
                }
            )
        elif payload.export_format == "individual_png":
            target = export_dir / "frames"
            target.mkdir()
            copied: list[str] = []
            for index, source in enumerate(frame_paths, start=1):
                destination = target / f"frame-{index:04d}.png"
                shutil.copy2(source, destination)
                copied.append(str(destination))
            file_result = {
                "path": str(target),
                "frame_width": max(int(frame["width"]) for frame in frames),
                "frame_height": max(int(frame["height"]) for frame in frames),
                "sheet_width": max(int(frame["width"]) for frame in frames),
                "sheet_height": max(int(frame["height"]) for frame in frames),
                "cells": [{"index": index, "path": path} for index, path in enumerate(copied)],
                "sha256": "directory-export",
            }
        else:
            raise RepositoryError("Use the code export endpoint for metadata and runtime code formats")

        metadata = self._metadata(animation, frames, payload, file_result)
        metadata_path = export_dir / f"{animation['slug']}.metadata.json"
        self.repository.atomic_write_bytes(metadata_path, (json.dumps(metadata, indent=2) + "\n").encode(), create_backup=False)
        record = {
            "id": export_id,
            "animation_id": animation["id"],
            "animation_name": animation["name"],
            "character": (animation.get("character") or {}).get("name", "Unknown"),
            "export_format": payload.export_format,
            "path": self.repository.relative(Path(file_result["path"])),
            "metadata_path": self.repository.relative(metadata_path),
            "frame_width": int(file_result["frame_width"]),
            "frame_height": int(file_result["frame_height"]),
            "sheet_width": int(file_result.get("sheet_width", file_result["frame_width"])),
            "sheet_height": int(file_result.get("sheet_height", file_result["frame_height"])),
            "frame_count": len(frames),
            "frame_rate": animation["frame_rate"],
            "loop_mode": animation["loop_mode"],
            "padding": payload.padding,
            "anchor": metadata["anchor"],
            "frame_durations": durations,
            "cells": file_result.get("cells", []),
            "sha256": file_result.get("sha256", ""),
            "asset_url": self._asset_url(Path(file_result["path"])),
            "metadata_url": self._asset_url(metadata_path),
            "official_use": bool(animation.get("approved")) and not bool(animation.get("technical_sample")),
            "warning": None if animation.get("approved") else "Draft export — not approved for production use",
            "created_at": _now(),
        }
        records = self.list_exports()
        records.append(record)
        backup = self.repository.write_json(
            SHEETS_PATH,
            records,
            schema_relative="schemas/sprite_sheet.schema.json",
            validate_each=True,
        )
        self._mark_exported(animation["id"])
        return record, backup

    def _metadata(
        self,
        animation: dict[str, Any],
        frames: list[dict[str, Any]],
        payload: SpriteSheetExportRequest,
        file_result: dict[str, Any],
    ) -> dict[str, Any]:
        cells = file_result.get("cells", [])
        if not cells:
            cells = [
                {"index": index, "x": 0, "y": 0, "width": frame["width"], "height": frame["height"]}
                for index, frame in enumerate(frames)
            ]
        return {
            "name": animation["slug"],
            "animationName": animation["name"],
            "character": (animation.get("character") or {}).get("name", "Unknown"),
            "frameWidth": int(file_result["frame_width"]),
            "frameHeight": int(file_result["frame_height"]),
            "frameCount": len(frames),
            "frameRate": animation["frame_rate"],
            "loop": animation["loop"],
            "loopMode": animation["loop_mode"],
            "anchor": {"x": frames[0]["anchor_x"], "y": frames[0]["anchor_y"]},
            "padding": payload.padding,
            "powerOfTwo": payload.power_of_two,
            "approved": bool(animation.get("approved")),
            "technicalSample": bool(animation.get("technical_sample")),
            "frames": [
                {
                    **cells[index],
                    "durationMs": int(frame["duration_ms"]),
                    "anchorX": frame["anchor_x"],
                    "anchorY": frame["anchor_y"],
                    "offsetX": frame["offset_x"],
                    "offsetY": frame["offset_y"],
                }
                for index, frame in enumerate(frames)
            ],
        }

    def _mark_exported(self, animation_id: str) -> None:
        records = self.sprites._animations()
        record = next(item for item in records if item.get("id") == animation_id)
        if record.get("approved"):
            record["status"] = "Exported"
        record["updated_at"] = _now()
        self.sprites._save_animations(records)

    def _asset_url(self, path: Path) -> str:
        relative = self.repository.relative(path)
        marker = "app-data/sprites/"
        return f"/sprite-assets/{relative.split(marker, 1)[1]}" if marker in relative else ""
