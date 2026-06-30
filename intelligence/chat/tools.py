from __future__ import annotations

import json
import logging
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from database.db_pool import intel_db_pool
from function.database_message_async import GetChatContext
from intelligence.memory.memory_manager_async import search_memories
from intelligence.profile.profile_manager_async import get_or_create_profile
from tools.tools import load_static_setting

from .models import ChatConfig, ChatTurn, ToolResult


def format_context_messages(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for index, message in enumerate(messages, start=1):
        role = str(message.get("role", "user"))
        content = " ".join(str(message.get("content", "")).split())
        if not content:
            continue
        lines.append(f"{index}. {role}: {content}")
    return "\n".join(lines)


def format_memories(memories: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for index, memory in enumerate(memories, start=1):
        content = " ".join(str(memory.get("content", "")).split())
        if not content:
            continue
        memory_type = str(memory.get("memory_type", "fact"))
        score = memory.get("importance_score", 0.5)
        title = str(memory.get("title") or "").strip()
        prefix = f"{title}: " if title and title not in content else ""
        relevance = memory.get("relevance")
        relevance_text = f",相关={round(float(relevance), 3)}" if isinstance(relevance, (int, float)) else ""
        lines.append(f"{index}. [{memory_type}/{score}{relevance_text}] {prefix}{content}")
    return "\n".join(lines)


async def query_memory_tool(turn: ChatTurn, query: str, limit: int) -> ToolResult:
    memories = await search_memories(
        user_id=turn.user_id,
        query=query or turn.text,
        limit=max(1, limit),
        mode="hybrid",
        context_id=turn.group_id,
    )
    if not memories:
        return ToolResult("query_memory", True, "未找到匹配的长期记忆。")
    return ToolResult(
        "query_memory",
        True,
        format_memories(memories),
        metadata={"count": len(memories)},
    )


def _parse_optional_time(value: str) -> int | None:
    value = str(value or "").strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    now = int(time.time())
    if value in {"今天", "今日"}:
        return now - 24 * 3600
    if value in {"昨天", "昨日"}:
        return now - 48 * 3600
    if value in {"最近", "近期"}:
        return now - 7 * 24 * 3600
    match = __import__("re").search(r"(\d+)\s*(天|小时|分钟)前", value)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        multiplier = {"分钟": 60, "小时": 3600, "天": 86400}[unit]
        return now - amount * multiplier
    return None


async def query_memory_advanced_tool(turn: ChatTurn, arguments: dict[str, Any], config: ChatConfig) -> ToolResult:
    mode = str(arguments.get("mode") or "hybrid")
    query = str(arguments.get("query") or turn.text)
    time_start = _parse_optional_time(str(arguments.get("time_start") or ""))
    time_end = _parse_optional_time(str(arguments.get("time_end") or "")) or None
    memories = await search_memories(
        user_id=turn.user_id,
        query=query,
        limit=int(arguments.get("limit") or config.memory_query_limit),
        mode=mode,
        context_id=turn.group_id,
        person_name=str(arguments.get("person_name") or ""),
        time_start=time_start,
        time_end=time_end,
    )
    if not memories:
        return ToolResult("query_memory", True, "未找到匹配的长期记忆。", metadata={"mode": mode})
    return ToolResult(
        "query_memory",
        True,
        format_memories(memories),
        metadata={"count": len(memories), "mode": mode},
    )


async def fetch_context_tool(turn: ChatTurn, limit: int) -> ToolResult:
    messages = await GetChatContext(turn.user_id, turn.group_id, limit=max(1, limit))
    if not messages:
        return ToolResult("fetch_context", True, "没有可用的近期上下文。")
    return ToolResult(
        "fetch_context",
        True,
        format_context_messages(messages),
        metadata={"count": len(messages)},
    )


async def fetch_history_tool(turn: ChatTurn, query: str, limit: int) -> ToolResult:
    rows = await __import__("database.db_pool", fromlist=["bot_db_pool"]).bot_db_pool.fetchall(
        """SELECT time, user_id, sender_nickname, raw_message, message_id
           FROM group_message
           WHERE group_id = ?
           ORDER BY time DESC
           LIMIT ?""",
        (turn.group_id, max(1, limit * 4)),
    )
    query_text = str(query or "").strip()
    messages: list[dict[str, Any]] = []
    for row in rows:
        content = str(row[3] or "")
        if query_text and query_text not in content:
            continue
        label = row[2] or str(row[1])
        messages.append(
            {
                "role": "user",
                "content": f"[{label}]: {content}",
                "message_id": row[4],
                "time": row[0],
            }
        )
        if len(messages) >= limit:
            break
    if not messages:
        return ToolResult("fetch_history", True, "没有找到匹配的历史消息。")
    return ToolResult(
        "fetch_history",
        True,
        format_context_messages(list(reversed(messages))),
        metadata={"count": len(messages)},
    )


async def query_person_profile_tool(turn: ChatTurn) -> ToolResult:
    profile = await get_or_create_profile(turn.user_id, turn.sender_nickname)
    parts: list[str] = []
    interests = profile.get("interests") or []
    if interests:
        parts.append(f"兴趣: {', '.join(map(str, interests[:8]))}")
    style = profile.get("interaction_style") or {}
    if style:
        parts.append(f"互动风格: {json.dumps(style, ensure_ascii=False)}")
    parts.append(f"熟悉度: {profile.get('familiarity_level', 0.3)}")
    parts.append(f"回复长度偏好: {profile.get('preferred_response_length', 'medium')}")
    return ToolResult(
        "query_person_profile",
        True,
        "\n".join(parts),
        metadata={"profile": profile},
    )


def _candidate_image_paths(query: str, max_count: int = 40) -> list[str]:
    roots = [Path("res")]
    meme_path = str(load_static_setting("meme_path", "") or "").strip()
    if meme_path:
        roots.append(Path(meme_path))
    suffixes = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    candidates: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in suffixes:
                candidates.append(path)
                if len(candidates) >= max_count:
                    break
        if len(candidates) >= max_count:
            break
    query_lower = query.lower()
    if query_lower:
        matched = [
            path for path in candidates
            if query_lower in path.stem.lower() or query in path.name
        ]
        if matched:
            candidates = matched
    random.shuffle(candidates)
    return [str(path) for path in candidates[:max_count]]


async def send_image_tool(turn: ChatTurn, query: str) -> ToolResult:
    paths = _candidate_image_paths(query)
    if not paths:
        return ToolResult("send_image", False, "没有找到可发送图片。")
    path = paths[0]
    return ToolResult(
        "send_image",
        True,
        f"已选择图片: {os.path.basename(path)}",
        metadata={"image_path": path},
    )


async def send_emoji_tool(turn: ChatTurn, query: str) -> ToolResult:
    try:
        from function.emoji_store import select_emoji_for_context

        selection = await select_emoji_for_context(
            group_id=turn.group_id,
            context_texts=[turn.text],
            request_text=query or turn.text,
        )
        if not selection.record:
            return ToolResult("send_emoji", False, selection.error or "没有选出表情包。")
        return ToolResult(
            "send_emoji",
            True,
            f"已选择表情包: {selection.record.description}",
            metadata={
                "emoji_path": selection.record.full_path,
                "emoji_hash": selection.record.image_hash,
                "reason": selection.reason,
            },
        )
    except Exception as exc:
        logging.error("选择表情包失败: %s", exc, exc_info=True)
        return ToolResult("send_emoji", False, f"选择表情包失败: {exc}")


async def execute_tool(
    action_name: str,
    *,
    turn: ChatTurn,
    config: ChatConfig,
    arguments: dict[str, Any] | None = None,
) -> ToolResult:
    arguments = arguments or {}
    try:
        if action_name == "query_memory":
            return await query_memory_advanced_tool(turn, arguments, config)
        if action_name == "query_person_profile":
            return await query_person_profile_tool(turn)
        if action_name == "fetch_context":
            return await fetch_context_tool(
                turn,
                int(arguments.get("limit") or config.context_limit),
            )
        if action_name == "fetch_history":
            return await fetch_history_tool(
                turn,
                str(arguments.get("query") or ""),
                int(arguments.get("limit") or config.history_limit),
            )
        if action_name == "send_image":
            return await send_image_tool(turn, str(arguments.get("query") or turn.text))
        if action_name == "send_emoji":
            return await send_emoji_tool(turn, str(arguments.get("query") or turn.text))
        return ToolResult(action_name, False, f"未知工具: {action_name}")
    except Exception as exc:
        logging.error("执行聊天工具失败: tool=%s error=%s", action_name, exc, exc_info=True)
        return ToolResult(action_name, False, f"工具执行失败: {exc}")


async def record_ai_chat_invocation(
    turn: ChatTurn,
    *,
    stage: str,
    model_name: str = "",
    provider: str = "",
    prompt: str = "",
    response: str = "",
    success: bool = True,
    error: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        await intel_db_pool.execute(
            """
            INSERT INTO ai_chat_invocation (
                created_at, group_id, user_id, message_id, stage, model_name,
                provider, prompt, response, success, error, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(datetime.now().timestamp()),
                turn.group_id,
                turn.user_id,
                turn.message_id,
                stage,
                model_name,
                provider,
                prompt[:6000],
                response[:6000],
                1 if success else 0,
                error[:1000],
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )
    except Exception as exc:
        logging.debug("记录 AI 调用日志失败: %s", exc)
