from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ChatRole = Literal["system", "user", "assistant", "tool"]
PlannerActionType = Literal[
    "reply",
    "query_memory",
    "query_person_profile",
    "fetch_context",
    "fetch_history",
    "send_image",
    "send_emoji",
    "wait",
]


@dataclass(slots=True)
class ChatConfig:
    enabled: bool = True
    planner_enabled: bool = True
    max_tool_rounds: int = 2
    enable_cloud_fallback: bool = False
    request_timeout_seconds: int = 60
    reply_max_tokens: int = 160
    planner_max_tokens: int = 300
    memory_query_limit: int = 5
    context_limit: int = 14
    history_limit: int = 20
    expression_learning_enabled: bool = True
    memory_embedding_enabled: bool = True


@dataclass(slots=True)
class ChatTurn:
    user_id: int
    group_id: int
    message_id: int
    text: str
    sender_nickname: str = ""
    reply_message_id: int = -1
    raw_message: dict[str, Any] | None = None
    websocket: Any = None

    @property
    def display_name(self) -> str:
        return self.sender_nickname or str(self.user_id)


@dataclass(slots=True)
class ModelMessage:
    role: ChatRole
    content: str
    images: list[str] = field(default_factory=list)

    def to_ollama(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.images:
            payload["images"] = self.images
        return payload


@dataclass(slots=True)
class PlannerAction:
    action: PlannerActionType
    reason: str = ""
    reply_guide: str = ""
    target_message_id: int | None = None
    query: str = ""
    limit: int | None = None
    mode: str = "hybrid"
    person_name: str = ""
    time_start: str = ""
    time_end: str = ""


@dataclass(slots=True)
class ToolResult:
    name: str
    success: bool
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ReplyResult:
    should_reply: bool
    text: str = ""
    reason: str = ""
    target_message_id: int | None = None
    model_name: str = ""
    image_path: str = ""
    emoji_path: str = ""
    used_tools: list[ToolResult] = field(default_factory=list)
    raw_planner_output: str = ""
