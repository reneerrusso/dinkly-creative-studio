from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CharacterType = Literal["dinko", "dinka", "shared", "prop", "effect"]
AnimationCategory = Literal[
    "idle",
    "facial",
    "movement",
    "emotion",
    "interaction",
    "prop_action",
    "sleep",
    "celebration",
    "shared",
    "environmental",
]
LoopMode = Literal["loop", "ping_pong", "play_once", "hold_last"]
ApprovalLevel = Literal["Draft", "Frame review", "Animation review", "Approved", "Deprecated"]
ReviewDecision = Literal["Pass", "Needs edit", "Reject", "Not reviewed"]


class SpriteCharacterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=80)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    character_type: CharacterType
    official_reference_paths: list[str] = Field(default_factory=list)
    default_canvas_width: int = Field(default=256, ge=16, le=4096)
    default_canvas_height: int = Field(default=256, ge=16, le=4096)
    default_anchor_x: float = Field(default=0.5, ge=0, le=1)
    default_anchor_y: float = Field(default=1.0, ge=0, le=1)
    default_frame_rate: float = Field(default=8, gt=0, le=60)
    approved: bool = False
    notes: str = ""


class SpriteCharacterUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=80)
    default_canvas_width: int | None = Field(default=None, ge=16, le=4096)
    default_canvas_height: int | None = Field(default=None, ge=16, le=4096)
    default_anchor_x: float | None = Field(default=None, ge=0, le=1)
    default_anchor_y: float | None = Field(default=None, ge=0, le=1)
    default_frame_rate: float | None = Field(default=None, gt=0, le=60)
    approved: bool | None = None
    notes: str | None = None


class SpriteAnimationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=100)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    character_id: str = Field(min_length=2)
    category: AnimationCategory
    description: str = Field(default="", max_length=500)
    frame_rate: float = Field(default=8, gt=0, le=60)
    loop: bool = True
    loop_mode: LoopMode = "loop"
    loop_start_frame: int = Field(default=0, ge=0, le=119)
    loop_end_frame: int | None = Field(default=None, ge=0, le=119)
    hold_first_frame_ms: int = Field(default=0, ge=0, le=10000)
    hold_last_frame_ms: int = Field(default=0, ge=0, le=10000)
    default_scale: float = Field(default=1, gt=0, le=4)
    expected_frame_count: int = Field(default=4, ge=1, le=120)
    default_anchor_x: float = Field(default=0.5, ge=0, le=1)
    default_anchor_y: float = Field(default=1.0, ge=0, le=1)
    tags: list[str] = Field(default_factory=list)
    required_layers: list[str] = Field(default_factory=list)
    optional_layers: list[str] = Field(default_factory=list)
    notes: str = ""
    technical_sample: bool = False

    @field_validator("tags", "required_layers", "optional_layers")
    @classmethod
    def unique_values(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))

    @model_validator(mode="after")
    def valid_loop_range(self) -> SpriteAnimationCreate:
        if self.loop_end_frame is not None and self.loop_end_frame < self.loop_start_frame:
            raise ValueError("loop_end_frame must be at or after loop_start_frame")
        return self


class SpriteAnimationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=100)
    category: AnimationCategory | None = None
    description: str | None = Field(default=None, max_length=500)
    frame_rate: float | None = Field(default=None, gt=0, le=60)
    loop: bool | None = None
    loop_mode: LoopMode | None = None
    loop_start_frame: int | None = Field(default=None, ge=0, le=119)
    loop_end_frame: int | None = Field(default=None, ge=0, le=119)
    hold_first_frame_ms: int | None = Field(default=None, ge=0, le=10000)
    hold_last_frame_ms: int | None = Field(default=None, ge=0, le=10000)
    default_scale: float | None = Field(default=None, gt=0, le=4)
    expected_frame_count: int | None = Field(default=None, ge=1, le=120)
    tags: list[str] | None = None
    required_layers: list[str] | None = None
    optional_layers: list[str] | None = None
    notes: str | None = None
    approval_level: ApprovalLevel | None = None


class SpriteFrameUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration_ms: int | None = Field(default=None, ge=16, le=10000)
    anchor_x: float | None = Field(default=None, ge=0, le=1)
    anchor_y: float | None = Field(default=None, ge=0, le=1)
    offset_x: int | None = Field(default=None, ge=-4096, le=4096)
    offset_y: int | None = Field(default=None, ge=-4096, le=4096)
    opacity: float | None = Field(default=None, ge=0, le=1)
    approved: bool | None = None
    review_status: ReviewDecision | None = None
    review_notes: str | None = Field(default=None, max_length=2000)


class FrameReorderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frame_ids: list[str] = Field(min_length=1)

    @field_validator("frame_ids")
    @classmethod
    def no_duplicate_frames(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("frame_ids must not contain duplicates")
        return value


class FrameAlignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["bottom_center", "selected_frame"]
    selected_frame_id: str | None = None

    @model_validator(mode="after")
    def require_selected_frame(self) -> FrameAlignRequest:
        if self.mode == "selected_frame" and not self.selected_frame_id:
            raise ValueError("selected_frame_id is required for selected_frame alignment")
        return self


class SpriteSheetExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    animation_id: str
    export_format: Literal[
        "horizontal",
        "vertical",
        "grid",
        "individual_png",
        "gif",
        "webp",
        "metadata_json",
        "css",
        "react",
        "remotion",
        "canvas",
    ] = "horizontal"
    padding: Literal[0, 2, 4, 8] = 2
    columns: int | None = Field(default=None, ge=1, le=64)
    power_of_two: bool = False


class CompositionLayer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    layer_type: Literal["background", "dinko", "dinka", "shared", "prop", "effect", "foreground", "text"]
    animation_id: str | None = None
    label: str
    x: float = 0.5
    y: float = 1
    scale: float = Field(default=1, gt=0, le=4)
    start_offset_ms: int = Field(default=0, ge=0)
    z_index: int = 0
    visible: bool = True
    settings: dict[str, Any] = Field(default_factory=dict)


class SpriteCompositionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=100)
    preset: str | None = None
    canvas_width: int = Field(default=1080, ge=64, le=4096)
    canvas_height: int = Field(default=1080, ge=64, le=4096)
    background_color: str = "warm cream"
    loop_duration_ms: int = Field(default=3000, ge=100, le=120000)
    layers: list[CompositionLayer] = Field(default_factory=list)
    notes: str = ""


class SpriteCompositionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=100)
    preset: str | None = None
    canvas_width: int | None = Field(default=None, ge=64, le=4096)
    canvas_height: int | None = Field(default=None, ge=64, le=4096)
    background_color: str | None = None
    loop_duration_ms: int | None = Field(default=None, ge=100, le=120000)
    layers: list[CompositionLayer] | None = None
    notes: str | None = None


class SharedInteractionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=100)
    dinko_animation_id: str
    dinka_animation_id: str
    shared_frame_rate: float = Field(default=8, gt=0, le=60)
    shared_duration: int = Field(default=1000, ge=100, le=120000)
    dinko_offset: dict[str, float] = Field(default_factory=lambda: {"x": -0.18, "y": 0})
    dinka_offset: dict[str, float] = Field(default_factory=lambda: {"x": 0.18, "y": 0})
    loop_mode: LoopMode = "loop"
    approved: bool = False
    notes: str = ""


class SharedInteractionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shared_frame_rate: float | None = Field(default=None, gt=0, le=60)
    shared_duration: int | None = Field(default=None, ge=100, le=120000)
    dinko_offset: dict[str, float] | None = None
    dinka_offset: dict[str, float] | None = None
    loop_mode: LoopMode | None = None
    approved: bool | None = None
    notes: str | None = None
