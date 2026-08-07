from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


class LearningRecord(BaseModel):
    learning_id: str
    pattern: str
    evidence_post_ids: list[str]
    confidence: Literal["high", "medium", "low"]
    metric_supported: bool
    hypothesis: str
    recommended_use: str
    avoid_overgeneralizing: str
    last_updated: date
    contradicts_learning_ids: list[str]
    status: Literal["active", "contradicted", "superseded", "testing"]

