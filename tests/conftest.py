from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.backend.config import Settings
from app.backend.services.repository_service import RepositoryService

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sprite_repository(tmp_path: Path) -> RepositoryService:
    for relative in (
        "data",
        "schemas",
        "scripts",
        "app-data/sprites",
        "app-data/sprites/exports",
        "app-data/sprites/thumbnails",
        "app-data/sprites/samples",
    ):
        (tmp_path / relative).mkdir(parents=True, exist_ok=True)
    for schema in ROOT.joinpath("schemas").glob("sprite_*.schema.json"):
        shutil.copy2(schema, tmp_path / "schemas" / schema.name)
    for name in ("sprite_characters", "sprite_animations", "sprite_sheets", "sprite_compositions"):
        shutil.copy2(ROOT / "data" / f"{name}.json", tmp_path / "data" / f"{name}.json")
    shutil.copy2(ROOT / "scripts" / "sprite_image_worker.py", tmp_path / "scripts" / "sprite_image_worker.py")
    (tmp_path / "app-data/sprites/frames.json").write_text("[]\n", encoding="utf-8")
    (tmp_path / "app-data/sprites/shared_interactions.json").write_text("[]\n", encoding="utf-8")
    return RepositoryService(Settings(tmp_path, "http://127.0.0.1:3000", 5 * 1024 * 1024))


@pytest.fixture
def technical_frame_bytes(sprite_repository: RepositoryService) -> list[bytes]:
    from app.backend.services.sprite_validation_service import SpriteValidationService

    service = SpriteValidationService(sprite_repository)
    output = sprite_repository.path("app-data/sprites/samples/test-frames")
    result = service.run_worker("technical_samples", {"output_dir": str(output)})
    return [Path(path).read_bytes() for path in result["paths"]]

