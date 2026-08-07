from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INSTAGRAM_ACTOR_ID = os.getenv("DINKLY_DEFAULT_INSTAGRAM_ACTOR_ID", "apify~instagram-scraper")
DEFAULT_TIKTOK_ACTOR_ID = os.getenv("DINKLY_DEFAULT_TIKTOK_ACTOR_ID", "clockworks~tiktok-profile-scraper")


@dataclass(frozen=True, slots=True)
class Settings:
    repository_root: Path
    frontend_origin: str
    max_upload_bytes: int
    app_mode: str = "local"
    public_base_url: str = "http://127.0.0.1:8000"
    database_url: str | None = None
    object_storage_url: str | None = None

    @property
    def app_data_dir(self) -> Path:
        return self.repository_root / "app-data"

    @property
    def uploads_dir(self) -> Path:
        return self.app_data_dir / "uploads"

    @property
    def backups_dir(self) -> Path:
        return self.app_data_dir / "backups"

    @property
    def reports_dir(self) -> Path:
        return self.app_data_dir / "reports"

    @property
    def sprites_dir(self) -> Path:
        return self.app_data_dir / "sprites"

    @property
    def generation_engine_dir(self) -> Path:
        return self.app_data_dir / "generation-engine"

    def safe_path(self, relative: str | Path) -> Path:
        candidate = (self.repository_root / relative).resolve()
        try:
            candidate.relative_to(self.repository_root)
        except ValueError as exc:
            raise ValueError("Path must remain inside the repository root") from exc
        return candidate

    def ensure_directories(self) -> None:
        for directory in (
            self.app_data_dir,
            self.uploads_dir,
            self.backups_dir,
            self.reports_dir,
            self.sprites_dir,
            self.generation_engine_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    root = Path(os.getenv("DINKLY_REPOSITORY_ROOT", DEFAULT_ROOT)).expanduser().resolve()
    max_mb = int(os.getenv("DINKLY_MAX_UPLOAD_MB", "15"))
    settings = Settings(
        repository_root=root,
        frontend_origin=os.getenv("DINKLY_FRONTEND_ORIGIN", "http://127.0.0.1:3000"),
        max_upload_bytes=max_mb * 1024 * 1024,
        app_mode=os.getenv("APP_MODE", "local").strip().lower(),
        public_base_url=os.getenv("DINKLY_PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
        database_url=os.getenv("DATABASE_URL") or None,
        object_storage_url=os.getenv("DINKLY_OBJECT_STORAGE_URL") or None,
    )
    settings.ensure_directories()
    return settings


settings = get_settings()
