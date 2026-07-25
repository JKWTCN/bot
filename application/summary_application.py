"""回复“{bot_name},有无省流”时，总结被引用的图片或聊天记录。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from data.application.application_info import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.GroupConfig import get_config
from function.group_operation import get_forward_message_data, get_message_data
from function.say import ReplySay
from intelligence.chat.config import load_ai_chat_config
from intelligence.chat.llm_client import ChatLLMClient
from intelligence.chat.models import ModelMessage
from tools.tools import load_setting


SUMMARY_COMMAND = "有无省流"
MAX_FORWARD_DEPTH = 3
MAX_RECORD_LINES = 120
MAX_RECORD_CHARS = 30_000
# 合并转发可能含大量图片，保留一个较高但有界的上限，
# 避免单次请求耗尽本地视觉模型的上下文/显存。
MAX_IMAGES = 12


def normalize_summary_command(text: str) -> str:
    """容忍空白和常见句末标点，但不会对包含其他内容的消息误触发。"""
    normalized = "".join((text or "").split())
    return normalized.rstrip("？?!。！~～")


def matches_summary_command(text: str, bot_name: str) -> bool:
    """匹配“{bot_name},有无省流”，兼容中英文逗号。"""
    normalized = normalize_summary_command(text)
    expected_prefix = "".join((bot_name or "").split())
    if not expected_prefix:
        return False
    return normalized in {
        f"{expected_prefix},{SUMMARY_COMMAND}",
        f"{expected_prefix}，{SUMMARY_COMMAND}",
    }


def _segments(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, str) and value.strip():
        return [{"type": "text", "data": {"text": value.strip()}}]
    return []


def _sender_name(node: dict[str, Any], index: int) -> str:
    sender = node.get("sender")
    if isinstance(sender, dict):
        return str(
            sender.get("card")
            or sender.get("nickname")
            or sender.get("user_id")
            or f"成员{index}"
        )
    return str(node.get("nickname") or node.get("name") or f"成员{index}")


class RepliedContentCollector:
    """把 OneBot 消息段整理成可给模型使用的文本和图片段。"""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.image_segments: list[dict[str, Any]] = []
        self.found_forward = False

    def add_line(self, line: str) -> None:
        text = " ".join(str(line).split()).strip()
        if not text or len(self.lines) >= MAX_RECORD_LINES:
            return
        current_length = sum(len(item) for item in self.lines)
        if current_length >= MAX_RECORD_CHARS:
            return
        self.lines.append(text[: max(0, MAX_RECORD_CHARS - current_length)])

    async def collect_segments(
        self,
        segments: list[dict[str, Any]],
        *,
        prefix: str = "",
        depth: int = 0,
    ) -> None:
        text_parts: list[str] = []
        for segment in segments:
            segment_type = str(segment.get("type") or "")
            data = segment.get("data")
            if not isinstance(data, dict):
                data = {}

            if segment_type == "text":
                text_parts.append(str(data.get("text") or ""))
            elif segment_type == "at":
                text_parts.append(f"@{data.get('name') or data.get('qq') or ''}")
            elif segment_type == "image":
                text_parts.append("[图片]")
                if len(self.image_segments) < MAX_IMAGES and data.get("url"):
                    self.image_segments.append(segment)
            elif segment_type == "face":
                text_parts.append(f"[表情:{data.get('raw') or data.get('id') or ''}]")
            elif segment_type in {"video", "record", "file"}:
                text_parts.append(f"[{segment_type}]")
            elif segment_type in {"forward", "node"}:
                if text_parts:
                    self.add_line(f"{prefix}{''.join(text_parts)}")
                    text_parts = []
                await self._collect_forward_segment(segment, depth=depth)
            elif data.get("text"):
                text_parts.append(str(data["text"]))

        if text_parts:
            self.add_line(f"{prefix}{''.join(text_parts)}")

    async def _collect_forward_segment(
        self, segment: dict[str, Any], *, depth: int
    ) -> None:
        if depth >= MAX_FORWARD_DEPTH:
            self.add_line("[合并转发层级过深，已省略]")
            return

        self.found_forward = True
        data = segment.get("data")
        if not isinstance(data, dict):
            data = {}

        nested = data.get("content")
        if isinstance(nested, list):
            if segment.get("type") == "node":
                await self.collect_segments(
                    _segments(nested),
                    prefix=f"{_sender_name(data, len(self.lines) + 1)}: ",
                    depth=depth + 1,
                )
            else:
                await self.collect_forward_nodes(nested, depth=depth + 1)
            return

        forward_id = data.get("id") or data.get("message_id") or data.get("resid")
        if forward_id is None:
            self.add_line("[合并转发内容无法展开]")
            return
        forward_data = await asyncio.to_thread(get_forward_message_data, forward_id)
        if not forward_data:
            self.add_line("[合并转发内容获取失败]")
            return
        nodes = forward_data.get("messages") or forward_data.get("message") or []
        await self.collect_forward_nodes(nodes, depth=depth + 1)

    async def collect_forward_nodes(self, nodes: Any, *, depth: int) -> None:
        if not isinstance(nodes, list):
            return
        for index, node in enumerate(nodes, start=1):
            if len(self.lines) >= MAX_RECORD_LINES:
                break
            if not isinstance(node, dict):
                continue
            data = node.get("data") if isinstance(node.get("data"), dict) else node
            content = data.get("content") or data.get("message") or []
            await self.collect_segments(
                _segments(content),
                prefix=f"{_sender_name(data, index)}: ",
                depth=depth,
            )


class SummaryApplication(GroupMessageApplication):
    def __init__(self):
        bot_name = str(load_setting("bot_name", "乐可"))
        super().__init__(
            ApplicationInfo(
                "AI省流总结",
                f"回复图片或聊天记录发送“{bot_name},有无省流”，生成内容摘要",
            ),
            200,
            False,
            ApplicationCostType.HIGH_TIME_HIGH_PERFORMANCE,
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        bot_name = str(load_setting("bot_name", "乐可"))
        return (
            message.replyMessageId != -1
            and matches_summary_command(message.plainTextMessage, bot_name)
            and get_config("enable_chat", message.groupId)
        )

    async def process(self, message: GroupMessageInfo):
        temp_image_paths: list[str] = []
        try:
            config = await load_ai_chat_config()
            if not config.enabled:
                await self._reply(message, "AI 聊天功能未开启。")
                return

            replied = await asyncio.to_thread(get_message_data, message.replyMessageId)
            if not replied:
                await self._reply(message, "没能读到被引用的消息，可能已被撤回或过期。")
                return

            collector = RepliedContentCollector()
            replied_segments = _segments(
                replied.get("message") or replied.get("raw_message") or []
            )
            await collector.collect_segments(replied_segments)
            if not collector.lines and not collector.image_segments:
                await self._reply(message, "这条消息里没有可以总结的内容。")
                return

            from intelligence.chat.runtime import download_images_from_segments

            image_paths = await download_images_from_segments(
                collector.image_segments,
                message_id=message.messageId,
                prefix="summary",
                temp_image_paths=temp_image_paths,
                limit=MAX_IMAGES,
            )
            if collector.image_segments and not image_paths and not collector.lines:
                await self._reply(message, "图片下载失败了，请稍后再试。")
                return

            source_text = "\n".join(collector.lines)
            source_kind = "合并聊天记录" if collector.found_forward else "被引用的消息"
            if image_paths and not source_text:
                source_kind = "图片"
            elif image_paths:
                source_kind += "（含图片）"

            prompt = f"""请为下面的{source_kind}生成一份中文“省流”总结。
要求：
1. 开头直接写“省流：”，先给出一句核心结论。
2. 如果信息较多，再用 3-5 个短要点补充；内容很少时不要强行列点。
3. 保留关键人物、数字、时间、结论和分歧，不要臆测图文中没有的信息。
4. 只输出总结，不要解释你的处理过程。
5. 使用场景是聊天,不要输出 md 格式或其他标记。

可提取的文本：
{source_text or "（无，请直接理解图片内容）"}"""

            client = ChatLLMClient(config)
            result = await client.generate(
                [
                    ModelMessage(
                        "system",
                        "你是准确、克制的内容摘要助手。",
                    ),
                    ModelMessage("user", prompt, images=image_paths),
                ],
                temperature=0.1,
                max_tokens=max(config.reply_max_tokens, 320),
                use_image_model=bool(image_paths),
            )
            await self._reply(message, result.content.strip())
        except Exception as exc:
            logging.error("AI 省流总结失败: %s", exc, exc_info=True)
            await self._reply(message, "省流失败了，请稍后再试。")
        finally:
            if temp_image_paths:
                from intelligence.chat.runtime import cleanup_temp_images

                cleanup_temp_images(temp_image_paths)

    @staticmethod
    async def _reply(message: GroupMessageInfo, text: str) -> None:
        await ReplySay(
            message.websocket,
            message.groupId,
            message.messageId,
            text,
        )
