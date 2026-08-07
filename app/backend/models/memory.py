from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MemoryType = Literal[
    "creative_preference",
    "prompt_learning",
    "qa_learning",
    "generation_learning",
    "failure_pattern",
    "concept_preference",
    "layout_learning",
    "model_learning",
    "performance_learning",
]


class AgentMemory(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    memory_type: MemoryType
    key: str
    summary: str
    value_json: dict[str, Any] = Field(default_factory=dict)
    confidence: Literal["high", "medium", "low"] = "low"
    source_type: str
    source_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    active: bool = True
    created_at: str
    updated_at: str


class MemoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str | None = Field(default=None, min_length=2, max_length=1000)
    value_json: dict[str, Any] | None = None
    confidence: Literal["high", "medium", "low"] | None = None
    active: bool | None = None


class BrainProposalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject", "edit"]
    edited_rule: str | None = Field(default=None, max_length=2000)
    reviewed_by: str = Field(default="Human reviewer", min_length=2, max_length=120)


class PerformanceSnapshotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    views: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    saves: int | None = Field(default=None, ge=0)


class MemoryQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=2, max_length=2000)


class BrainProposalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str = Field(min_length=3, max_length=160)
    target_file: Literal[
        "CREATIVE_BIBLE.md",
        "CHARACTER_BIBLE.md",
        "STYLE_GUIDE.md",
        "NANO_BANANA_RULES.md",
        "FAILURES.md",
    ]
