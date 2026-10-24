"""AI 群聊应用入口。

具体的 MaiBot 风格 planner/replyer/tool loop 位于 intelligence.chat.runtime。
这里仅保留应用注册、触发判断和旧 chat(...) 兼容接口。
"""

from __future__ import annotations
from config.ai_control import AIDisabledError, ai_enabled

import json
import asyncio
import logging
import random
from typing import Any

from data.application.application_info import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.GroupConfig import get_config
from function.say import ReplySay, ReplySayTextImage
from intelligence.chat.models import ChatTurn
from intelligence.chat.runtime import handle_chat_turn, handle_group_chat
from intelligence.chat_quality.reply_policy import (
    REPLY_NECESSITY_TRIGGER_SCORE,
    should_reply_random_candidate,
)
from tools.tools import load_setting
from intelligence.chat_quality.random_chat import RandomChatLimiter, candidate_kind


def getPrompts() -> str:
    """兼容旧调用方的 prompt 读取函数。"""
    with open("prompts.json", "r", encoding="utf-8") as f:
        prompts = json.load(f)
    return str(prompts)


def load_chat_quality_config(group_id: int | None = None) -> dict[str, Any]:
    try:
        with open("intelligence_config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        chat_quality = config.get("chat_quality", {})
        if not isinstance(chat_quality, dict):
            return {}
        overrides = chat_quality.get("group_overrides", {}).get(str(group_id), {})
        return {**chat_quality, **overrides}
    except Exception as exc:
        logging.warning("读取聊天质量配置失败,使用默认值: %s", exc)
        return {}


async def chat(
    websocket,
    user_id: int,
    group_id: int,
    message_id: int,
    text: str,
    reply_message_id: int = -1,
    sender_nickname: str = "",
    raw_message: dict | None = None,
):
    """旧接口兼容: 生成 AI 回复并发送引用回复。"""
    if not ai_enabled():
        return
    turn = ChatTurn(
        websocket=websocket,
        user_id=user_id,
        group_id=group_id,
        message_id=message_id,
        text=text,
        reply_message_id=reply_message_id,
        sender_nickname=sender_nickname,
        raw_message=raw_message,
    )
    try:
        result = await handle_chat_turn(turn)
    except AIDisabledError:
        return
    except Exception as exc:
        logging.error("AI聊天运行失败: %s", exc, exc_info=True)
        await ReplySay(websocket, group_id, message_id, "呜呜不太理解呢喵.")
        return

    if not result or not result.should_reply or not result.text:
        return
    image_path = result.emoji_path or result.image_path
    if image_path:
        await ReplySayTextImage(
            websocket,
            group_id,
            result.target_message_id or message_id,
            result.text,
            image_path,
        )
    else:
        await ReplySay(websocket, group_id, result.target_message_id or message_id, result.text)


class GroupChatApplication(GroupMessageApplication):
    """群聊 AI 对话应用。"""

    def __init__(self):
        application_info = ApplicationInfo("ai聊天功能", "ai根据上下文聊天回复")
        super().__init__(
            application_info,
            0,
            True,
            ApplicationCostType.HIGH_TIME_HIGH_PERFORMANCE,
        )
        self.random_limiter = RandomChatLimiter()

    async def process(self, message: GroupMessageInfo):
        trigger = getattr(message, "_ai_chat_trigger", "direct")
        if trigger == "quoted":
            from function.group_operation import get_message_data

            quoted = await asyncio.to_thread(get_message_data, message.replyMessageId)
            sender = (quoted or {}).get("sender") or {}
            bot_id = getattr(message, "botId", load_setting("bot_id", 0))
            is_bot_reply = bool(bot_id) and str(sender.get("user_id", "")) == str(bot_id)
            # Some adapters include the group ID; never accept a different group.
            if quoted and quoted.get("group_id") is not None:
                is_bot_reply = is_bot_reply and str(quoted["group_id"]) == str(message.groupId)
            if not is_bot_reply:
                if not self._judge_random(message, load_chat_quality_config(message.groupId)):
                    return
                trigger = "random"
        sent = False
        try:
            sent = bool(await self._process_chat(message))
        finally:
            if trigger == "random":
                self.random_limiter.finish(message.groupId, sent=sent)
                logging.info("随机聊天结果: group=%s message=%s sent=%s",
                             message.groupId, message.messageId, sent)

    async def _process_chat(self, message: GroupMessageInfo):
        if not ai_enabled():
            return
        try:
            result = await handle_group_chat(message)
        except AIDisabledError:
            return
        except Exception as exc:
            logging.error("AI聊天应用处理失败: %s", exc, exc_info=True)
            if getattr(message, "_ai_chat_trigger", "") == "random":
                return False
            await ReplySay(
                message.websocket,
                message.groupId,
                message.messageId,
                "呜呜不太理解呢喵.",
            )
            return

        if not result or not result.should_reply or not result.text:
            return
        image_path = result.emoji_path or result.image_path
        if image_path:
            await ReplySayTextImage(
                message.websocket,
                message.groupId,
                result.target_message_id or message.messageId,
                result.text,
                image_path,
            )
        else:
            await ReplySay(
                message.websocket,
                message.groupId,
                result.target_message_id or message.messageId,
                result.text,
            )
        return True

    def judge(self, message: GroupMessageInfo) -> bool:
        if not ai_enabled():
            return False
        message._ai_chat_trigger = "direct"
        if not get_config("enable_chat", message.groupId):
            return False

        bot_name = load_setting("bot_name", "乐可")
        bot_id = load_setting("bot_id", 0)
        if (
            (bot_name in message.plainTextMessage or bot_id in message.atList)
            and get_config("replay_chat", message.groupId)
        ):
            return True

        chat_quality = load_chat_quality_config(message.groupId)
        if (chat_quality.get("random_chat_policy", {}).get("enabled", False)
                and chat_quality["random_chat_policy"].get("reply_to_bot", True)
                and get_config("replay_chat", message.groupId)
                and message.replyMessageId != -1):
            message._ai_chat_trigger = "quoted"
            return True
        return self._judge_random(message, chat_quality)

    def _judge_random(self, message: GroupMessageInfo, chat_quality: dict) -> bool:
        policy = chat_quality.get("random_chat_policy", {})
        if policy.get("enabled", False):
            if not get_config("random_chat", message.groupId):
                return False
            kind = candidate_kind(message.plainTextMessage)
            if not kind:
                logging.debug("随机聊天跳过无效内容: group=%s message=%s", message.groupId, message.messageId)
                return False
            # Questions need 50 points; meaningful statements retain their 40-point base.
            threshold = int(policy.get("question_threshold", 50) if kind == "question"
                            else policy.get("normal_threshold", 40))
            score = should_reply_random_candidate(
                message.plainTextMessage, bot_name=load_setting("bot_name", "乐可"),
                trigger_threshold=threshold,
                effective_frequency=float(chat_quality.get("random_reply_frequency", 1.0)),
            )
            probability = float(policy.get("question_probability", 0.20) if kind == "question"
                                else policy.get("normal_probability", 0.03))
            if score.score < threshold or random.random() >= probability:
                logging.debug("随机聊天未选中: group=%s kind=%s probability=%.3f %s",
                              message.groupId, kind, probability, score.detail)
                return False
            if not self.random_limiter.reserve(message.groupId, policy):
                logging.info("随机聊天限流: group=%s message=%s", message.groupId, message.messageId)
                return False
            message._ai_chat_trigger = "random"
            logging.info("随机聊天候选通过: group=%s user=%s kind=%s probability=%.3f %s",
                         message.groupId, message.senderId, kind, probability, score.detail)
            return True

        bot_name = load_setting("bot_name", "乐可")
        if random.random() < 0.005 and get_config("random_chat", message.groupId):
            threshold = int(
                chat_quality.get(
                    "reply_necessity_threshold",
                    REPLY_NECESSITY_TRIGGER_SCORE,
                )
            )
            score = should_reply_random_candidate(
                message.plainTextMessage,
                bot_name=bot_name,
                trigger_threshold=threshold,
                effective_frequency=float(chat_quality.get("random_reply_frequency", 1.0)),
            )
            if score.score >= threshold:
                logging.info(
                    "随机聊天候选通过: group=%s user=%s %s",
                    message.groupId,
                    message.senderId,
                    score.detail,
                )
                return True
            logging.info(
                "随机聊天候选跳过: group=%s user=%s %s",
                message.groupId,
                message.senderId,
                score.detail,
            )
        return False
