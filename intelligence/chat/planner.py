from __future__ import annotations

import json
import logging
import re
from typing import Any

from tools.tools import load_setting

from .llm_client import ChatLLMClient
from .models import ChatConfig, ChatTurn, ModelMessage, PlannerAction, ToolResult
from .tools import format_context_messages, record_ai_chat_invocation


PLANNER_SYSTEM_PROMPT = """你是群聊机器人的行动规划器,不是最终发言者。
你只能输出 JSON,不要输出 markdown。

可选 action:
- reply: 需要正式回复用户。
- query_memory: 回复依赖长期记忆时先检索记忆。
- query_person_profile: 回复依赖用户画像/偏好时查询画像。
- fetch_context: 当前上下文不足时获取更多近期消息。
- fetch_history: 需要更长聊天历史时检索历史消息。
- send_image: 用户明确要图,或回复更适合配图时选择图片。
- send_emoji: 回复更适合使用表情包时选择表情。
- wait: 不需要回复。

JSON 格式:
{"action":"reply|query_memory|query_person_profile|fetch_context|fetch_history|send_image|send_emoji|wait","reason":"简短原因","reply_guide":"给回复器的指引","query":"检索词","mode":"hybrid","person_name":"","time_start":"","time_end":"","limit":5}
"""


VALID_ACTIONS = {
    "reply",
    "query_memory",
    "query_person_profile",
    "fetch_context",
    "fetch_history",
    "send_image",
    "send_emoji",
    "wait",
}


def _extract_json_object(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?", "", candidate).strip()
        candidate = re.sub(r"```$", "", candidate).strip()
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def parse_planner_action(text: str, *, fallback_message_id: int) -> PlannerAction:
    parsed = _extract_json_object(text)
    if not parsed:
        return PlannerAction(
            action="reply",
            reason="planner 输出无法解析,按直接回复处理",
            reply_guide="直接回应用户最新消息,保持简短自然。",
            target_message_id=fallback_message_id,
        )

    action = str(parsed.get("action") or "reply").strip()
    if action not in VALID_ACTIONS:
        action = "reply"

    target_message_id = parsed.get("target_message_id")
    try:
        target_message_id = int(target_message_id) if target_message_id is not None else fallback_message_id
    except (TypeError, ValueError):
        target_message_id = fallback_message_id

    limit = parsed.get("limit")
    try:
        limit = int(limit) if limit is not None else None
    except (TypeError, ValueError):
        limit = None

    return PlannerAction(
        action=action,  # type: ignore[arg-type]
        reason=str(parsed.get("reason") or "").strip(),
        reply_guide=str(parsed.get("reply_guide") or "").strip(),
        target_message_id=target_message_id,
        query=str(parsed.get("query") or "").strip(),
        limit=limit,
        mode=str(parsed.get("mode") or "hybrid").strip() or "hybrid",
        person_name=str(parsed.get("person_name") or "").strip(),
        time_start=str(parsed.get("time_start") or "").strip(),
        time_end=str(parsed.get("time_end") or "").strip(),
    )


class ChatPlanner:
    def __init__(self, llm_client: ChatLLMClient, config: ChatConfig):
        self.llm_client = llm_client
        self.config = config

    async def plan(
        self,
        turn: ChatTurn,
        *,
        context_messages: list[dict[str, Any]],
        tool_results: list[ToolResult],
    ) -> PlannerAction:
        if not self.config.planner_enabled:
            return PlannerAction(
                action="reply",
                reason="planner disabled",
                reply_guide="直接回应用户最新消息,保持简短自然。",
                target_message_id=turn.message_id,
            )

        bot_name = load_setting("bot_name", "乐可")
        tool_result_text = "\n\n".join(
            f"[{result.name}] {'成功' if result.success else '失败'}\n{result.content}"
            for result in tool_results
        )
        user_prompt = f"""机器人名称: {bot_name}
群号: {turn.group_id}
当前用户: {turn.display_name}({turn.user_id})
当前消息ID: {turn.message_id}
当前消息: {turn.text}

近期上下文:
{format_context_messages(context_messages) or "无"}

已执行工具结果:
{tool_result_text or "无"}

请判断下一步 action。若已经有足够信息,选择 reply。若用户提到“记得/之前/上次/喜欢/约定”,优先 query_memory。
若需要画像选 query_person_profile；需要更久聊天记录选 fetch_history；适合表情包选 send_emoji；明确要图片选 send_image。
若当前消息只是短反应、无须机器人插话,选择 wait。
"""
        messages = [
            ModelMessage("system", PLANNER_SYSTEM_PROMPT),
            ModelMessage("user", user_prompt),
        ]
        try:
            result = await self.llm_client.generate(
                messages,
                temperature=0.1,
                max_tokens=self.config.planner_max_tokens,
            )
            await record_ai_chat_invocation(
                turn,
                stage="planner",
                model_name=result.model_name,
                provider=result.provider,
                prompt=user_prompt,
                response=result.content,
            )
            return parse_planner_action(result.content, fallback_message_id=turn.message_id)
        except Exception as exc:
            logging.error("planner 执行失败,降级为直接回复: %s", exc)
            await record_ai_chat_invocation(
                turn,
                stage="planner",
                prompt=user_prompt,
                success=False,
                error=str(exc),
            )
            return PlannerAction(
                action="reply",
                reason="planner failed",
                reply_guide="直接回应用户最新消息,保持简短自然。",
                target_message_id=turn.message_id,
            )
