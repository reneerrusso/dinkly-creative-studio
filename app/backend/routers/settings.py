from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.backend.services.repository_service import RepositoryService

router = APIRouter(prefix="/api/settings", tags=["settings"])
repository = RepositoryService()


class StudioSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_background_family: str = Field(min_length=1, max_length=80)
    default_accent_color: str = Field(min_length=1, max_length=80)
    default_prompt_format: str = Field(min_length=1, max_length=80)
    default_output_folder: str = Field(min_length=1, max_length=160)
    show_advanced_scoring: bool = True
    require_qa_before_approval: bool = True

    @field_validator("default_output_folder")
    @classmethod
    def safe_output_folder(cls, value: str) -> str:
        resolved = repository.path(value)
        if not value.startswith("app-data/"):
            raise ValueError("Export folders must stay under app-data/")
        if resolved == repository.root:
            raise ValueError("Export folder cannot be the repository root")
        return value


@router.get("")
def get_settings() -> dict:
    payload = repository.read_json("app-data/settings.json", {})
    return StudioSettings.model_validate(payload).model_dump(mode="json")


@router.put("")
def update_settings(payload: StudioSettings) -> dict:
    backup = repository.write_json("app-data/settings.json", payload.model_dump(mode="json"))
    return {"settings": payload.model_dump(mode="json"), "backup": backup}
