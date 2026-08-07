from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INSTAGRAM_ACTOR_ID = os.getenv("DINKLY_DEFAULT_INSTAGRAM_ACTOR_ID", "apify~instagram-scraper")
DEFAULT_TIKTOK_ACTOR_ID = os.getenv("DINKLY_DEFAULT_TIKTOK_ACTOR_ID", "clockworks~tiktok-profile-scraper")


@dataclass(frozen=True, slots=True)
class Settings:
    repository_root: Path
    frontend_origin: str
    max_upload_bytes: int
    app_url: str | None = None
    app_mode: str = "local"
    public_base_url: str = "http://127.0.0.1:8000"
    database_url: str | None = None
    object_storage_url: str | None = None
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "dinkly-assets"
    api_url: str = "http://127.0.0.1:8000"
    allowed_origins: tuple[str, ...] = ()
    cloud_task_runner_url: str | None = None
    cloud_task_token: str | None = None
    cloud_scheduler_token: str | None = None
    learning_maximum_cost_per_task: float = 0.25
    learning_daily_budget: float = 1.0
    learning_monthly_budget: float = 10.0

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
    frontend_origin = os.getenv("DINKLY_FRONTEND_ORIGIN", "http://127.0.0.1:3000").rstrip("/")
    app_mode = os.getenv("APP_MODE", "local").strip().lower()
    if app_mode not in {"local", "cloud"}:
        raise ValueError("APP_MODE must be local or cloud")
    app_url = (os.getenv("APP_URL") or (frontend_origin if app_mode == "local" else None))
    api_url = (os.getenv("API_URL") or os.getenv("DINKLY_PUBLIC_BASE_URL") or "http://127.0.0.1:8000").rstrip("/")
    extra_origins = tuple(
        value.strip().rstrip("/")
        for value in os.getenv("DINKLY_ALLOWED_ORIGINS", "").split(",")
        if value.strip()
    )
    allowed_origins = tuple(dict.fromkeys((frontend_origin, *(value for value in (app_url, *extra_origins) if value))))
    if app_mode == "cloud":
        for label, value in (("APP_URL", app_url), ("API_URL", api_url)):
            parsed = urlsplit(value or "")
            if parsed.scheme != "https" or not parsed.hostname or parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError(f"{label} must be a public HTTPS URL in cloud mode")
    settings = Settings(
        repository_root=root,
        frontend_origin=frontend_origin,
        max_upload_bytes=max_mb * 1024 * 1024,
        app_url=app_url,
        app_mode=app_mode,
        public_base_url=api_url,
        database_url=os.getenv("DATABASE_URL") or None,
        object_storage_url=os.getenv("DINKLY_OBJECT_STORAGE_URL") or None,
        supabase_url=(os.getenv("SUPABASE_URL") or None),
        supabase_service_role_key=(os.getenv("SUPABASE_SERVICE_ROLE_KEY") or None),
        supabase_storage_bucket=os.getenv("SUPABASE_STORAGE_BUCKET", "dinkly-assets").strip() or "dinkly-assets",
        api_url=api_url,
        allowed_origins=allowed_origins,
        cloud_task_runner_url=(os.getenv("CLOUD_TASK_RUNNER_URL") or None),
        cloud_task_token=(os.getenv("CLOUD_TASK_TOKEN") or None),
        cloud_scheduler_token=(os.getenv("CLOUD_SCHEDULER_TOKEN") or None),
        learning_maximum_cost_per_task=float(os.getenv("DINKLY_LEARNING_MAX_COST_PER_TASK", "0.25")),
        learning_daily_budget=float(os.getenv("DINKLY_LEARNING_DAILY_BUDGET", "1.0")),
        learning_monthly_budget=float(os.getenv("DINKLY_LEARNING_MONTHLY_BUDGET", "10.0")),
    )
    settings.ensure_directories()
    return settings


settings = get_settings()
