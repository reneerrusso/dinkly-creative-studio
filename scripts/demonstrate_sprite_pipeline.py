#!/usr/bin/env python3
"""Create a clearly labeled, non-official technical sprite sample and export it."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def main() -> int:
    from app.backend.models.sprites import SpriteAnimationCreate, SpriteSheetExportRequest
    from app.backend.services.repository_service import RepositoryService
    from app.backend.services.sprite_export_service import SpriteExportService
    from app.backend.services.sprite_service import SpriteService

    repository = RepositoryService()
    sprites = SpriteService(repository)
    existing = next(
        (
            item
            for item in sprites.list_animations(include_drafts=True)
            if item.get("slug") == "dinko-technical-blink-pipeline-v2"
        ),
        None,
    )
    if existing:
        animation = existing
    else:
        animation, _ = sprites.create_animation(
            SpriteAnimationCreate(
                name="Dinko Blink - technical pipeline sample v2",
                slug="technical-blink-pipeline-v2",
                character_id="sprite-character-dinko",
                category="facial",
                description="Simple labeled shapes for upload, timing, transparency, and export testing. Not DINKLY artwork.",
                frame_rate=8,
                loop=True,
                loop_mode="loop",
                expected_frame_count=3,
                tags=["technical-sample", "blink-pipeline"],
                notes="TECHNICAL SAMPLE - NOT OFFICIAL. Never approve or use as character artwork.",
                technical_sample=True,
            )
        )
    if not animation.get("frames"):
        with tempfile.TemporaryDirectory(prefix="dinkly-technical-sprite-") as directory:
            result = sprites.validation.run_worker("technical_samples", {"output_dir": directory})
            uploads = [(Path(path).name, Path(path).read_bytes()) for path in result["paths"]]
            sprites.upload_frames(animation["id"], uploads)
        animation = sprites.get_animation(animation["id"])
    export, _ = SpriteExportService(repository).export(
        SpriteSheetExportRequest(
            animation_id=animation["id"],
            export_format="horizontal",
            padding=2,
        )
    )
    metadata = json.loads(repository.path(export["metadata_path"]).read_text(encoding="utf-8"))
    print(json.dumps({"animation": animation, "export": export, "metadata": metadata}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
