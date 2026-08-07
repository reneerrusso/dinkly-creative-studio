from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SocialPostInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    title: str = Field(min_length=1)
    platform: str | None = None
    post_date: date | None = None
    views: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    saves: int | None = Field(default=None, ge=0)
    follows_generated: int | None = Field(default=None, ge=0)
    watch_time: float | None = Field(default=None, ge=0)
    completion_rate: float | None = Field(default=None, ge=0, le=1)
    format: str | None = None
    storyline: str | None = None
    left_panel_summary: str | None = None
    right_panel_summary: str | None = None
    caption: str | None = None
    text_on_image: list[str] | None = None
    background_color: str | None = None
    accent_color: str | None = None
    camera_angle: str | None = None
    character_count: int | None = Field(default=None, ge=0)
    props: list[str] | None = None
    emotional_theme: str | None = None
    brand_integration: str | None = None
    uploaded_asset_reference: str | None = None
    notes: str | None = None
    uploaded_asset_hash: str | None = None

    @field_validator("text_on_image", "props")
    @classmethod
    def unique_items(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("Items must be unique")
        return value


class SocialPostUploadResponse(BaseModel):
    path: str
    sha256: str
    size: int
    original_name: str

