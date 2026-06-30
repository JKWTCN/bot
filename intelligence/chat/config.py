from __future__ import annotations

import logging
from typing import Any

from config.config_cache import get_intelligence_config

from .models import ChatConfig


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if value is None:
        return default
    return bool(value)


def _coerce_int(value: Any, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(value))
    except (TypeError, ValueError):
        return default


async def load_ai_chat_config() -> ChatConfig:
    """Load chat runtime config with conservative defaults."""
    try:
        config = await get_intelligence_config()
    except Exception as exc:
        logging.warning("读取 ai_chat 配置失败,使用默认值: %s", exc)
        config = {}

    raw_ai_chat = config.get("ai_chat", {})
    if not isinstance(raw_ai_chat, dict):
        raw_ai_chat = {}

    return ChatConfig(
        enabled=_coerce_bool(raw_ai_chat.get("enabled"), True),
        planner_enabled=_coerce_bool(raw_ai_chat.get("planner_enabled"), True),
        max_tool_rounds=_coerce_int(raw_ai_chat.get("max_tool_rounds"), 2, minimum=0),
        enable_cloud_fallback=_coerce_bool(raw_ai_chat.get("enable_cloud_fallback"), False),
        request_timeout_seconds=_coerce_int(raw_ai_chat.get("request_timeout_seconds"), 60),
        reply_max_tokens=_coerce_int(raw_ai_chat.get("reply_max_tokens"), 160),
        planner_max_tokens=_coerce_int(raw_ai_chat.get("planner_max_tokens"), 300),
        memory_query_limit=_coerce_int(raw_ai_chat.get("memory_query_limit"), 5),
        context_limit=_coerce_int(raw_ai_chat.get("context_limit"), 14),
        history_limit=_coerce_int(raw_ai_chat.get("history_limit"), 20),
        expression_learning_enabled=_coerce_bool(
            raw_ai_chat.get("expression_learning_enabled"),
            True,
        ),
        memory_embedding_enabled=_coerce_bool(
            raw_ai_chat.get("memory_embedding_enabled"),
            True,
        ),
    )
