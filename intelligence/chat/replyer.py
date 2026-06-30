from __future__ import annotations

import json
import logging
from typing import Any

from intelligence.personalization.prompt_builder import PromptBuilder
from intelligence.expression.expression_learner import get_expression_guidance

from .llm_client import ChatLLMClient
from .models import ChatConfig, ChatTurn, ModelMessage, PlannerAction, ReplyResult, ToolResult
from .tools import format_context_messages, format_memories, record_ai_chat_invocation


DETAILED_REPLY_KEYWORDS = (
    "详细",
    "展开",
    "分析",
    "步骤",
    "解释",
    "讲讲",
    "长一点",
    "完整",
    "教程",
    "代码",
    "方案",
    "为什么",
)


def wants_detailed_reply(text: str) -> bool:
    return any(keyword in text for keyword in DETAILED_REPLY_KEYWORDS)


def build_reply_style_guard(text: str) -> str:
    if wants_detailed_reply(text):
        return (
            "用户明确要求解释时可以适度详细,但先给结论。"
            "最多 3 个短要点,总长度尽量控制在 120 字内。"
            "不要写开场白或总结。每句话结尾加'喵'。"
        )
    return (
        "默认按群聊短回复处理。严格控制在 10-30 字,只回应最关键的一点。"
        "不要解释判断过程,不要列点。每句话结尾加'喵'。"
    )


def load_base_prompt() -> str:
    with open("prompts.json", "r", encoding="utf-8") as f:
        return json.dumps(json.load(f), ensure_ascii=False)


class ChatReplyer:
    def __init__(self, llm_client: ChatLLMClient, config: ChatConfig):
        self.llm_client = llm_client
        self.config = config

    async def generate_reply(
        self,
        turn: ChatTurn,
        *,
        action: PlannerAction,
        context_messages: list[dict[str, Any]],
        user_profile: dict[str, Any],
        memories: list[dict[str, Any]],
        tool_results: list[ToolResult],
        image_paths: list[str],
    ) -> ReplyResult:
        prompt_builder = PromptBuilder()
        system_prompt = prompt_builder.build_personalized_prompt(
            base_prompt=load_base_prompt(),
            user_profile=user_profile,
            memories=memories,
            context_summary=None,
            current_user_name=turn.sender_nickname,
        )
        tool_reference = "\n\n".join(
            f"[{result.name}]\n{result.content}" for result in tool_results if result.content
        )
        memory_reference = format_memories(memories)
        expression_guidance = await get_expression_guidance(turn.group_id, turn.user_id)
        selected_image_path = ""
        selected_emoji_path = ""
        for tool_result in tool_results:
            selected_image_path = selected_image_path or str(tool_result.metadata.get("image_path") or "")
            selected_emoji_path = selected_emoji_path or str(tool_result.metadata.get("emoji_path") or "")
        user_content = f"""当前要回复的对象: {turn.display_name}({turn.user_id})
当前消息ID: {turn.message_id}
当前消息: {turn.text}

planner 指引:
{action.reply_guide or action.reason or "直接自然回复。"}

回复风格:
{build_reply_style_guard(turn.text)}

近期上下文:
{format_context_messages(context_messages) or "无"}

长期记忆:
{memory_reference or "无"}

表达学习参考:
{expression_guidance or "无"}

工具结果:
{tool_reference or "无"}

发送素材:
{"将随回复附带图片/表情,正文可以更短。" if (selected_image_path or selected_emoji_path) else "无"}

请只输出要发到群里的正文。"""

        messages = [
            ModelMessage("system", system_prompt),
            ModelMessage("user", user_content, images=image_paths),
        ]
        use_image_model = bool(image_paths)
        try:
            result = await self.llm_client.generate(
                messages,
                temperature=0.2,
                max_tokens=self.config.reply_max_tokens,
                use_image_model=use_image_model,
            )
        except Exception as exc:
            if image_paths:
                logging.error("带图片生成回复失败,降级纯文本: %s", exc)
                messages[-1].images = []
                result = await self.llm_client.generate(
                    messages,
                    temperature=0.2,
                    max_tokens=self.config.reply_max_tokens,
                )
            else:
                raise

        reply_text = " ".join(result.content.split())
        await record_ai_chat_invocation(
            turn,
            stage="replyer",
            model_name=result.model_name,
            provider=result.provider,
            prompt=user_content,
            response=reply_text,
            metadata={"use_image_model": use_image_model},
        )
        return ReplyResult(
            should_reply=True,
            text=reply_text,
            reason=action.reason,
            target_message_id=action.target_message_id or turn.message_id,
            model_name=result.model_name,
            image_path=selected_image_path,
            emoji_path=selected_emoji_path,
            used_tools=tool_results,
        )
