from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from typing import Any

from data.message.group_message_info import GroupMessageInfo
from intelligence.context.context_manager_async import get_smart_context
from intelligence.expression.expression_learner import learn_expression_from_messages
from intelligence.memory.memory_manager_async import (
    retrieve_relevant_memories,
    store_episode_from_messages,
)
from intelligence.memory.smart_extractor import extract_and_store_memory_smart
from intelligence.profile.profile_extractor import ProfileExtractor
from intelligence.profile.profile_manager_async import get_or_create_profile, update_profile

from .config import load_ai_chat_config
from .llm_client import ChatLLMClient
from .models import ChatTurn, PlannerAction, ReplyResult, ToolResult
from .planner import ChatPlanner
from .replyer import ChatReplyer
from .tools import execute_tool, fetch_context_tool


background_tasks: set[asyncio.Task[Any]] = set()


def create_tracked_task(coro) -> asyncio.Task[Any]:
    task = asyncio.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return task


def image_segments_from_message(raw_message: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not raw_message:
        return []
    segments = raw_message.get("message", [])
    if not isinstance(segments, list):
        return []
    return [segment for segment in segments if segment.get("type") == "image"]


def safe_temp_image_name(prefix: str, message_id: int | str, index: int, file_name: str) -> str:
    base_name = os.path.basename(file_name or "image")
    base_name = re.sub(r"[^A-Za-z0-9_.-]", "_", base_name)[-80:] or "image"
    return f"{prefix}_{message_id}_{index}_{uuid.uuid4().hex[:8]}_{base_name}"


def normalize_image_for_ollama(image_path: str) -> str | None:
    if not os.path.exists(image_path) or os.path.getsize(image_path) == 0:
        logging.error("图片文件不存在或为空: %s", image_path)
        return None

    normalized_path = f"{os.path.splitext(image_path)[0]}_ollama.jpg"
    try:
        from PIL import Image

        with Image.open(image_path) as img:
            img.seek(0)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(normalized_path, format="JPEG", quality=92)
        return normalized_path
    except Exception as exc:
        logging.error("图片转换失败: %s error=%s", image_path, exc)
        return None


async def download_images_from_segments(
    segments: list[dict[str, Any]],
    *,
    message_id: int | str,
    prefix: str,
    temp_image_paths: list[str],
    limit: int = 4,
) -> list[str]:
    from function.image_processor import getImagePathByFile

    image_paths: list[str] = []
    for index, segment in enumerate(segments):
        if len(image_paths) >= limit:
            break
        data = segment.get("data", {})
        if not isinstance(data, dict):
            continue
        url = data.get("url")
        if not url:
            continue
        file_name = safe_temp_image_name(prefix, message_id, index, str(data.get("file", "image")))
        try:
            raw_path = await asyncio.to_thread(getImagePathByFile, file_name, url)
            temp_image_paths.append(raw_path)
            normalized_path = await asyncio.to_thread(normalize_image_for_ollama, raw_path)
        except Exception as exc:
            logging.error("下载图片失败: message_id=%s error=%s", message_id, exc)
            continue
        if normalized_path:
            temp_image_paths.append(normalized_path)
            image_paths.append(normalized_path)
    return image_paths


async def collect_current_images(turn: ChatTurn, temp_image_paths: list[str]) -> list[str]:
    image_paths = await download_images_from_segments(
        image_segments_from_message(turn.raw_message),
        message_id=turn.message_id,
        prefix="current",
        temp_image_paths=temp_image_paths,
    )

    if turn.reply_message_id != -1:
        try:
            from function.group_operation import get_reply_image_url
            from function.image_processor import getImagePathByFile

            image_url = await asyncio.to_thread(get_reply_image_url, turn.reply_message_id)
            if image_url:
                raw_path = await asyncio.to_thread(
                    getImagePathByFile,
                    f"reply_{turn.message_id}_{uuid.uuid4().hex[:8]}.image",
                    image_url,
                )
                temp_image_paths.append(raw_path)
                normalized_path = await asyncio.to_thread(normalize_image_for_ollama, raw_path)
                if normalized_path:
                    temp_image_paths.append(normalized_path)
                    image_paths.append(normalized_path)
        except Exception as exc:
            logging.error("处理引用图片失败: message_id=%s error=%s", turn.message_id, exc)

    return image_paths


def cleanup_temp_images(temp_image_paths: list[str]) -> None:
    for path in dict.fromkeys(temp_image_paths):
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as exc:
                logging.debug("删除临时图片失败: %s error=%s", path, exc)


async def update_profile_background(turn: ChatTurn, user_profile: dict[str, Any]) -> None:
    try:
        extractor = ProfileExtractor()
        features = extractor.extract_from_message(turn.text, turn.user_id)
        updates = extractor.merge_with_existing_profile(user_profile, features)
        if updates:
            await update_profile(turn.user_id, updates)
    except Exception as exc:
        logging.error("后台更新画像失败: %s", exc, exc_info=True)


async def extract_memory_background(turn: ChatTurn) -> None:
    try:
        if len(turn.text.strip()) <= 10:
            return
        await extract_and_store_memory_smart(
            user_id=turn.user_id,
            message=turn.text,
            context_type="group",
            context_id=turn.group_id,
        )
    except Exception as exc:
        logging.error("后台提取记忆失败: %s", exc, exc_info=True)


async def learn_expression_background(turn: ChatTurn, context_messages: list[dict[str, Any]]) -> None:
    try:
        await learn_expression_from_messages(
            group_id=turn.group_id,
            user_id=turn.user_id,
            current_text=turn.text,
            context_messages=context_messages,
        )
    except Exception as exc:
        logging.debug("后台表达学习失败: %s", exc, exc_info=True)


async def store_episode_background(turn: ChatTurn, context_messages: list[dict[str, Any]]) -> None:
    try:
        await store_episode_from_messages(
            group_id=turn.group_id,
            user_id=turn.user_id,
            person_name=turn.display_name,
            messages=context_messages,
        )
    except Exception as exc:
        logging.debug("后台 episode 写入失败: %s", exc, exc_info=True)


async def build_context_and_profile(turn: ChatTurn) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    user_profile = await get_or_create_profile(turn.user_id, turn.sender_nickname)
    try:
        context_result = await get_smart_context(
            user_id=turn.user_id,
            group_id=turn.group_id,
            user_profile=user_profile,
            current_message=turn.text,
        )
        context_messages = list(context_result.get("messages", []))
    except Exception as exc:
        logging.error("智能上下文获取失败,使用普通上下文: %s", exc, exc_info=True)
        context_result = await fetch_context_tool(turn, 10)
        context_messages = []
        if context_result.metadata.get("count"):
            from function.database_message_async import GetChatContext

            context_messages = await GetChatContext(turn.user_id, turn.group_id, 10)

    memories = await retrieve_relevant_memories(turn.user_id, turn.text, limit=5)
    return user_profile, context_messages, memories


async def handle_chat_turn(turn: ChatTurn) -> ReplyResult | None:
    config = await load_ai_chat_config()
    if not config.enabled:
        return None

    temp_image_paths: list[str] = []
    try:
        user_profile, context_messages, memories = await build_context_and_profile(turn)
        create_tracked_task(update_profile_background(turn, user_profile))
        create_tracked_task(extract_memory_background(turn))
        create_tracked_task(store_episode_background(turn, context_messages))
        if config.expression_learning_enabled:
            create_tracked_task(learn_expression_background(turn, context_messages))

        llm_client = ChatLLMClient(config)
        planner = ChatPlanner(llm_client, config)
        replyer = ChatReplyer(llm_client, config)
        tool_results: list[ToolResult] = []

        action = PlannerAction(
            action="reply",
            reason="default",
            reply_guide="直接回应用户最新消息,保持简短自然。",
            target_message_id=turn.message_id,
        )
        for round_index in range(config.max_tool_rounds + 1):
            action = await planner.plan(
                turn,
                context_messages=context_messages,
                tool_results=tool_results,
            )
            if action.action == "wait":
                return ReplyResult(
                    should_reply=False,
                    reason=action.reason,
                    raw_planner_output=action.reason,
                    used_tools=tool_results,
                )
            if action.action == "reply":
                break
            if round_index >= config.max_tool_rounds:
                action = PlannerAction(
                    action="reply",
                    reason="工具轮次达到上限",
                    reply_guide="基于已有上下文和工具结果简短回复。",
                    target_message_id=turn.message_id,
                )
                break

            result = await execute_tool(
                action.action,
                turn=turn,
                config=config,
                arguments={
                    "query": action.query or turn.text,
                    "limit": action.limit,
                    "mode": action.mode,
                    "person_name": action.person_name,
                    "time_start": action.time_start,
                    "time_end": action.time_end,
                },
            )
            tool_results.append(result)

        image_paths = await collect_current_images(turn, temp_image_paths)
        return await replyer.generate_reply(
            turn,
            action=action,
            context_messages=context_messages,
            user_profile=user_profile,
            memories=memories,
            tool_results=tool_results,
            image_paths=image_paths,
        )
    finally:
        cleanup_temp_images(temp_image_paths)


async def handle_group_chat(message: GroupMessageInfo) -> ReplyResult | None:
    turn = ChatTurn(
        websocket=message.websocket,
        user_id=message.senderId,
        group_id=message.groupId,
        message_id=message.messageId,
        text=message.plainTextMessage,
        reply_message_id=message.replyMessageId,
        sender_nickname=getattr(message, "senderNickname", ""),
        raw_message=message.rawMessage,
    )
    return await handle_chat_turn(turn)
