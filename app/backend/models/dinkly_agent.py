from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AgentVisualState = Literal[
    "idle",
    "learning",
    "preparing",
    "generating",
    "reviewing",
    "repairing",
    "waiting_for_human",
    "success",
    "error",
]

ExpressionState = Literal[
    "idle",
    "learning",
    "generating",
    "reviewing",
    "repairing",
    "waiting",
    "success",
    "error",
]

AgentSourceChannel = Literal["web", "slack", "scheduled", "learning"]
AgentTaskType = Literal[
    "generate_concepts",
    "generate_comic",
    "repair_comic",
    "review_comic",
    "learn",
    "brain_query",
    "feedback",
    "approval",
    "custom",
]
AgentTaskStatus = Literal[
    "queued",
    "running",
    "cancellation_requested",
    "waiting_for_human",
    "completed",
    "failed",
    "cancelled",
]


class AgentSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maximum_task_runtime_seconds: int | None = Field(default=None, ge=30, le=86400)


class AgentTask(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    source_channel: AgentSourceChannel
    source_thread_id: str
    source_user_id: str | None = None
    source_message_id: str | None = None
    user_instruction: str
    task_type: AgentTaskType
    status: AgentTaskStatus = "queued"
    priority: int = Field(ge=1, le=6)
    context: dict[str, Any] = Field(default_factory=dict)
    run_ids: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    approval_required: bool = False
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None


class AgentConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    channel: Literal["web", "slack"]
    thread_id: str
    user_id: str | None = None
    message: str
    role: Literal["user", "agent", "system"]
    created_at: str
    linked_run_ids: list[str] = Field(default_factory=list)
    linked_artifact_ids: list[str] = Field(default_factory=list)
    linked_task_ids: list[str] = Field(default_factory=list)


class AgentInstructionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=2, max_length=1000)
    user_id: str = Field(default="owner", min_length=1, max_length=120)
    thread_id: str = Field(default="web-default", min_length=1, max_length=200)
    notify_slack: bool = False
    context: dict[str, Any] = Field(default_factory=dict)


class AgentApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "pass", "reject", "fix", "try_another", "more_like_this", "edit"]
    item_type: Literal["concept", "comic", "brain_update"]
    item_id: str = Field(min_length=2, max_length=200)
    notes: str | None = Field(default=None, max_length=500)
    source_channel: Literal["web", "slack"] = "web"
    source_thread_id: str | None = None


class SlackConnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bot_token: str = Field(min_length=10, max_length=500)
    signing_secret: str = Field(min_length=8, max_length=500)
    app_token: str | None = Field(default=None, min_length=10, max_length=500)
    mode: Literal["events_api", "socket_mode"] = "events_api"
    default_channel: str | None = Field(default=None, max_length=120)
    allowed_users: list[str] = Field(default_factory=list, max_length=50)


class SlackSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["events_api", "socket_mode"]
    default_channel: str | None = Field(default=None, max_length=120)
    allowed_users: list[str] = Field(default_factory=list, max_length=50)
    notifications: dict[str, bool] = Field(default_factory=dict)


class DinklyAgentChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=2, max_length=500)


class DinklyLearningRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    force: bool = False
