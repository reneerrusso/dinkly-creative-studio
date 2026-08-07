from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.backend.models.sprites import SpriteSheetExportRequest
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.sprite_sheet_service import SHEETS_PATH, SpriteSheetService

IMAGE_EXPORTS = {"horizontal", "vertical", "grid", "individual_png", "gif", "webp"}


class SpriteExportService:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository
        self.sheets = SpriteSheetService(repository)

    def list(self) -> list[dict[str, Any]]:
        return self.sheets.list_exports()

    def export(self, payload: SpriteSheetExportRequest) -> tuple[dict[str, Any], str | None]:
        if payload.export_format in IMAGE_EXPORTS:
            return self.sheets.export(payload)
        animation = self.sheets.sprites.get_animation(payload.animation_id)
        frames = animation.get("frames", [])
        if not frames:
            raise RepositoryError("Upload frames before exporting animation metadata")
        export_id = f"sprite-export-{uuid.uuid4().hex[:12]}"
        directory = self.repository.path(f"app-data/sprites/exports/{export_id}")
        directory.mkdir(parents=True, exist_ok=False)
        metadata = self._generic_metadata(animation, frames)
        extension, content = self._code_content(payload.export_format, metadata)
        output = directory / f"{animation['slug']}.{extension}"
        self.repository.atomic_write_bytes(output, content.encode(), create_backup=False)
        metadata_path = directory / f"{animation['slug']}.metadata.json"
        self.repository.atomic_write_bytes(
            metadata_path,
            (json.dumps(metadata, indent=2) + "\n").encode(),
            create_backup=False,
        )
        width = max(int(frame["width"]) for frame in frames)
        height = max(int(frame["height"]) for frame in frames)
        record = {
            "id": export_id,
            "animation_id": animation["id"],
            "animation_name": animation["name"],
            "character": (animation.get("character") or {}).get("name", "Unknown"),
            "export_format": payload.export_format,
            "path": self.repository.relative(output),
            "metadata_path": self.repository.relative(metadata_path),
            "frame_width": width,
            "frame_height": height,
            "sheet_width": width,
            "sheet_height": height,
            "frame_count": len(frames),
            "frame_rate": animation["frame_rate"],
            "loop_mode": animation["loop_mode"],
            "padding": payload.padding,
            "anchor": metadata["anchor"],
            "frame_durations": [frame["duration_ms"] for frame in frames],
            "cells": metadata["frames"],
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "asset_url": self._asset_url(output),
            "metadata_url": self._asset_url(metadata_path),
            "official_use": bool(animation.get("approved")) and not bool(animation.get("technical_sample")),
            "warning": None if animation.get("approved") else "Draft export — not approved for production use",
            "created_at": datetime.now(UTC).isoformat(),
        }
        records = self.sheets.list_exports()
        records.append(record)
        backup = self.repository.write_json(
            SHEETS_PATH,
            records,
            schema_relative="schemas/sprite_sheet.schema.json",
            validate_each=True,
        )
        return record, backup

    def _generic_metadata(self, animation: dict[str, Any], frames: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "name": animation["slug"],
            "frameRate": animation["frame_rate"],
            "loop": animation["loop"],
            "loopMode": animation["loop_mode"],
            "anchor": {"x": frames[0]["anchor_x"], "y": frames[0]["anchor_y"]},
            "approved": bool(animation.get("approved")),
            "technicalSample": bool(animation.get("technical_sample")),
            "frames": [
                {
                    "index": index,
                    "x": 0,
                    "y": 0,
                    "width": frame["width"],
                    "height": frame["height"],
                    "durationMs": frame["duration_ms"],
                    "image": Path(frame["image_path"]).name,
                }
                for index, frame in enumerate(frames)
            ],
        }

    def _code_content(self, export_format: str, metadata: dict[str, Any]) -> tuple[str, str]:
        encoded = json.dumps(metadata, indent=2)
        frame_count = len(metadata["frames"])
        duration = sum(frame["durationMs"] for frame in metadata["frames"])
        if export_format == "metadata_json":
            return "json", encoded + "\n"
        if export_format == "css":
            return (
                "css",
                f".dinkly-{metadata['name']} {{\n"
                f"  animation: dinkly-{metadata['name']} {duration}ms steps({frame_count}) infinite;\n"
                "  background-repeat: no-repeat;\n"
                "}\n\n"
                f"@keyframes dinkly-{metadata['name']} {{\n"
                "  from { background-position-x: 0; }\n"
                f"  to {{ background-position-x: calc(-1 * var(--frame-width) * {frame_count}); }}\n"
                "}\n",
            )
        if export_format == "react":
            return (
                "tsx",
                "import { useEffect, useState } from \"react\";\n\n"
                f"const metadata = {encoded} as const;\n\n"
                f"export function {self._component_name(metadata['name'])}() {{\n"
                "  const [frame, setFrame] = useState(0);\n"
                "  useEffect(() => {\n"
                "    const timer = window.setTimeout(() => setFrame(value => (value + 1) % metadata.frames.length), metadata.frames[frame].durationMs);\n"
                "    return () => window.clearTimeout(timer);\n"
                "  }, [frame]);\n"
                "  return <img alt=\"\" src={metadata.frames[frame].image} />;\n"
                "}\n",
            )
        if export_format == "remotion":
            return "remotion.json", json.dumps({"type": "remotion-sprite-asset", "asset": metadata}, indent=2) + "\n"
        if export_format == "canvas":
            return (
                "js",
                f"export const sprite = {encoded};\n\n"
                "export function drawSprite(ctx, image, frameIndex, x, y, scale = 1) {\n"
                "  const frame = sprite.frames[frameIndex % sprite.frames.length];\n"
                "  ctx.drawImage(image, frame.x, frame.y, frame.width, frame.height, x, y, frame.width * scale, frame.height * scale);\n"
                "}\n",
            )
        raise RepositoryError("Unsupported sprite code export format")

    def _component_name(self, slug: str) -> str:
        return "".join(part.capitalize() for part in slug.split("-")) + "Sprite"

    def _asset_url(self, path: Path) -> str:
        relative = self.repository.relative(path)
        return f"/sprite-assets/{relative.split('app-data/sprites/', 1)[1]}"

