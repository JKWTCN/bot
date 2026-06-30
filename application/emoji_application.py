"""VLM-judged emoji collection and sending applications."""

import logging
import re

from data.application.application_info import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.GroupConfig import get_config
from function.emoji_store import (
    collect_emoji_from_url,
    extract_image_urls,
    select_emoji_for_context,
)
from function.say import ReplySay, ReplySayImage
from tools.tools import HasKeyWords


EMOJI_SEND_KEYWORDS = (
    "发个表情包",
    "发送表情包",
    "来个表情包",
    "表情包来",
    "整点表情包",
    "抽个表情包",
    "表情包",
)


class EmojiCollectApplication(GroupMessageApplication):
    """Collect incoming image emojis after VLM review and tagging."""

    def __init__(self):
        application_info = ApplicationInfo(
            "表情包偷取",
            "自动审核并收藏群内表情包",
            trigger="发送图片/表情包",
            detail="收到群图片后,使用视觉模型审核并提取情绪标签,合格后静默加入表情包库。",
            category="娱乐",
            params=[
                "emoji_collect",
                "emoji_content_review",
                "emoji_max_size_mb",
                "emoji_max_count",
            ],
        )
        super().__init__(
            application_info,
            1,
            True,
            ApplicationCostType.HIGH_TIME_LOW_PERFORMANCE,
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        if not get_config("emoji_collect", message.groupId):
            return False
        return bool(extract_image_urls(message.rawMessage))

    async def process(self, message: GroupMessageInfo):
        urls = extract_image_urls(message.rawMessage)
        for url in urls:
            result = await collect_emoji_from_url(
                url,
                group_id=message.groupId,
                user_id=message.senderId,
                message_id=message.messageId,
            )
            logging.info(
                "表情包收藏结果: group=%s user=%s status=%s hash=%s desc=%s reason=%s",
                message.groupId,
                message.senderId,
                result.status,
                result.image_hash,
                result.description,
                result.reason,
            )


class EmojiSendApplication(GroupMessageApplication):
    """Send a VLM-selected emoji for the current context."""

    def __init__(self):
        application_info = ApplicationInfo(
            "发送表情包",
            "根据上下文用视觉模型选择表情包发送",
            trigger="发个表情包 / 来个表情包 / 表情包",
            detail="触发后会把候选表情包拼成带编号图片,交给视觉模型按当前语境选择一张发送。",
            category="娱乐",
            params=["emoji_send", "emoji_candidate_count"],
        )
        super().__init__(
            application_info,
            45,
            False,
            ApplicationCostType.HIGH_TIME_HIGH_PERFORMANCE,
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        if not get_config("emoji_send", message.groupId):
            return False
        if message.imageFileList:
            return False
        return HasKeyWords(message.plainTextMessage, list(EMOJI_SEND_KEYWORDS))

    async def process(self, message: GroupMessageInfo):
        context_texts = await self._get_recent_context(message)
        selection = await select_emoji_for_context(
            group_id=message.groupId,
            context_texts=context_texts,
            request_text=self._build_request_text(message.plainTextMessage),
        )
        if selection.record is None:
            await ReplySay(message.websocket, message.groupId, message.messageId, selection.error)
            return
        logging.info(
            "模型选择表情包: group=%s hash=%s desc=%s reason=%s",
            message.groupId,
            selection.record.image_hash,
            selection.record.description,
            selection.reason,
        )
        await ReplySayImage(
            message.websocket,
            message.groupId,
            message.messageId,
            selection.record.full_path,
        )

    async def _get_recent_context(self, message: GroupMessageInfo) -> list[str]:
        try:
            from function.database_message_async import GetChatContext

            context_messages = await GetChatContext(message.senderId, message.groupId)
        except Exception as e:
            logging.warning(f"获取表情包上下文失败: {e}")
            return [message.plainTextMessage]

        context_texts = []
        for context_message in context_messages[-5:]:
            content = str(context_message.get("content", "")).strip()
            if content:
                context_texts.append(content)
        context_texts.append(message.plainTextMessage)
        return context_texts

    def _build_request_text(self, text: str) -> str:
        request_text = text.strip()
        for keyword in EMOJI_SEND_KEYWORDS:
            request_text = request_text.replace(keyword, " ")
        request_text = re.sub(r"\s+", " ", request_text).strip()
        return request_text or text.strip()

