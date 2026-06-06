"""
AI聊天应用模块 (深度优化版本)
优化内容:
1. 移除所有threading，使用纯asyncio
2. 使用异步数据库连接池
3. 使用配置缓存
4. 智能记忆提取策略
"""

import asyncio
import json
import logging
import os
import random
import re
import uuid
from typing import Any, cast

import requests

from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.GroupConfig import get_config
from function.say import SayRaw, ReplySay
from function.database_message_async import GetChatContext
from function.database_group_async import GetGroupName
from tools.tools import (
    load_chat_ai_model,
    load_chat_ai_thinking,
    load_image_ai_model,
    load_image_ai_thinking,
    load_setting,
    load_static_setting,
)

from tools.tools import GetNCWCPort, GetNCHSPort, GetOllamaPort

# 创建任务集合跟踪后台任务
background_tasks = set()

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

DIRECT_CONTEXT_IMAGE_LIMIT = 4


def create_tracked_task(coro):
    """创建被跟踪的后台任务"""
    task = asyncio.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return task


def wants_detailed_reply(text: str) -> bool:
    """判断用户是否明确要求展开说明。"""
    return any(keyword in text for keyword in DETAILED_REPLY_KEYWORDS)


def build_reply_style_guard(text: str) -> str:
    """构建回复长度和重点约束。"""
    if wants_detailed_reply(text):
        return (
            "回复风格要求: 用户明确要求解释或展开时,可以适度详细,但必须先给结论。"
            "最多写3个短要点,总长度尽量控制在120字内。"
            "不要写开场白、背景铺垫或总结。"
            "保持每句话结尾加'喵'。"
        )

    return (
        "回复风格要求: 默认按群聊短回复处理。"
        "必须严格控制在10-30字,只回答最关键的信息。"
        "不要解释背景,不要列多个要点,不要输出长段文字。"
        "保持每句话结尾加'喵'。"
    )


def get_response_token_limit(text: str) -> int:
    """限制生成预算,不对模型输出做事后裁剪。"""
    return 160 if wants_detailed_reply(text) else 64


def is_same_local_chat_and_image_model() -> bool:
    """判断聊天模型是否可直接接收图片上下文。"""
    if not load_setting("use_local_ai", True):
        return False
    return load_chat_ai_model() == load_image_ai_model()


def strip_context_metadata(message: dict[str, Any]) -> dict[str, object]:
    """去掉只在本地用于回查图片的元数据。"""
    clean_message: dict[str, object] = {
        "role": message.get("role", "user"),
        "content": message.get("content", ""),
    }
    if message.get("images"):
        clean_message["images"] = message["images"]
    return clean_message


def strip_image_descriptions(content: str) -> str:
    """同模型直传图片时,避免继续依赖预识别的图片描述。"""
    return re.sub(r"\[图片内容:[^\]]*\]", "[图片]", content)


def image_segments_from_message(raw_message: dict | None) -> list[dict]:
    """从 OneBot 消息中取出图片段。"""
    if not raw_message:
        return []
    segments = raw_message.get("message", [])
    if not isinstance(segments, list):
        return []
    return [seg for seg in segments if seg.get("type") == "image"]


def safe_temp_image_name(prefix: str, message_id: int | str, index: int, file: str) -> str:
    """生成临时图片文件名,避免原始 file 字段包含路径分隔符。"""
    base_name = os.path.basename(file or "image")
    base_name = re.sub(r"[^A-Za-z0-9_.-]", "_", base_name)[-80:] or "image"
    return f"{prefix}_{message_id}_{index}_{uuid.uuid4().hex[:8]}_{base_name}"


def normalize_image_for_ollama(image_path: str) -> str | None:
    """校验图片并转换成 Ollama 稳定支持的 JPEG。"""
    if not os.path.exists(image_path) or os.path.getsize(image_path) == 0:
        logging.error(f"图片文件不存在或为空: {image_path}")
        return None

    normalized_path = f"{os.path.splitext(image_path)[0]}_ollama.jpg"

    try:
        from PIL import Image

        with Image.open(image_path) as img:
            img.seek(0)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            elif img.mode == "L":
                img = img.convert("RGB")
            img.save(normalized_path, format="JPEG", quality=92)
        return normalized_path
    except Exception as pil_error:
        logging.warning(f"PIL转换图片失败,尝试OpenCV: {image_path}, error={pil_error}")

    try:
        import cv2
        import numpy as np

        image_data = np.fromfile(image_path, dtype=np.uint8)
        img = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
        if img is None:
            logging.error(f"图片无法解码: {image_path}")
            return None
        if not cv2.imwrite(normalized_path, img):
            logging.error(f"图片转换写入失败: {normalized_path}")
            return None
        return normalized_path
    except Exception as cv_error:
        logging.error(f"转换图片失败: {image_path}, error={cv_error}")
        return None


def fetch_message_segments(message_id: int) -> list[dict]:
    """通过 NapCat/OneBot get_msg 回取历史消息段。"""
    payload = {"message_id": message_id}
    response = requests.post(
        f"http://localhost:{GetNCHSPort()}/get_msg",
        json=payload,
        timeout=10,
    )
    data = response.json()
    if data.get("status") != "ok":
        return []
    segments = data.get("data", {}).get("message", [])
    return segments if isinstance(segments, list) else []


async def download_images_from_segments(
    segments: list[dict],
    message_id: int | str,
    prefix: str,
    temp_image_paths: list[str],
    remaining_limit: int,
) -> list[str]:
    """下载图片段为 Ollama 可读取的临时文件路径。"""
    if remaining_limit <= 0:
        return []

    from function.image_processor import getImagePathByFile

    image_paths: list[str] = []
    for index, segment in enumerate(segments):
        if len(image_paths) >= remaining_limit:
            break
        if segment.get("type") != "image":
            continue

        data = segment.get("data", {})
        url = data.get("url")
        if not url:
            continue

        file_name = safe_temp_image_name(
            prefix, message_id, index, str(data.get("file", "image"))
        )
        try:
            raw_image_path = await asyncio.to_thread(getImagePathByFile, file_name, url)
            temp_image_paths.append(raw_image_path)
            image_path = await asyncio.to_thread(
                normalize_image_for_ollama, raw_image_path
            )
        except Exception as e:
            logging.error(f"下载上下文图片失败: message_id={message_id}, error={e}")
            continue

        if image_path is None:
            continue

        image_paths.append(image_path)
        temp_image_paths.append(image_path)

    return image_paths


def remove_images_from_messages(messages: list[dict[str, object]]) -> list[dict[str, object]]:
    """移除图片字段,用于图片加载失败后的文本重试。"""
    clean_messages: list[dict[str, object]] = []
    for message in messages:
        clean_messages.append(
            {key: value for key, value in message.items() if key != "images"}
        )
    return clean_messages


async def build_context_messages_for_model(
    context_messages: list[dict[str, Any]],
    current_message_id: int,
    temp_image_paths: list[str],
    direct_image_context: bool,
) -> list[dict[str, object]]:
    """构建实际传给模型的上下文消息。"""
    if not direct_image_context:
        return [strip_context_metadata(message) for message in context_messages]

    messages: list[dict[str, object]] = []
    used_image_count = 0
    for message in context_messages:
        message_id = message.get("message_id")
        if message_id == current_message_id:
            continue

        clean_message = strip_context_metadata(message)
        clean_message["content"] = strip_image_descriptions(str(clean_message["content"]))

        if (
            clean_message.get("role") == "user"
            and message_id is not None
            and "[图片" in str(message.get("content", ""))
            and used_image_count < DIRECT_CONTEXT_IMAGE_LIMIT
        ):
            try:
                segments = await asyncio.to_thread(fetch_message_segments, int(message_id))
                image_paths = await download_images_from_segments(
                    image_segments_from_message({"message": segments}),
                    message_id,
                    "context",
                    temp_image_paths,
                    DIRECT_CONTEXT_IMAGE_LIMIT - used_image_count,
                )
                if image_paths:
                    clean_message["images"] = image_paths
                    used_image_count += len(image_paths)
            except Exception as e:
                logging.error(f"回取上下文图片失败: message_id={message_id}, error={e}")

        messages.append(clean_message)

    return messages


def getPrompts() -> str:
    """获取系统提示词"""
    with open("prompts.json", "r", encoding="utf-8") as f:
        prompts = json.load(f)
    return str(prompts)


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
    """AI聊天功能回复 (深度优化版 - 纯异步)

    性能优化:
    - 移除threading，使用asyncio.create_task
    - 使用异步数据库连接池
    - 使用配置缓存
    - 智能记忆提取过滤

    Args:
        websocket: 回复的websocket
        user_id: 用户的id
        group_id: 群的id
        message_id: 消息id
        text: 传入信息,在ai回复后追加在后面
        reply_message_id: 引用的消息ID,如果有则检查是否包含图片
    """
    model = load_chat_ai_model()
    thinking = load_chat_ai_thinking()
    image_path = None
    temp_image_paths: list[str] = []
    direct_image_context = is_same_local_chat_and_image_model()
    target_user_label = sender_nickname if sender_nickname else str(user_id)
    target_user_guard = (
        "你正在群聊中回复单个用户。"
        f"本轮你要回复的对象是【{target_user_label}】。"
        "历史中其他昵称代表其他人。"
        "当你使用“你/你的”时，只能指向本轮对象。"
        "不得把其他人的行为、偏好、经历归因给本轮对象。"
        "若需引用他人，请明确写出对方昵称。"
    )
    reply_style_guard = build_reply_style_guard(text)
    response_token_limit = get_response_token_limit(text)

    # 检查是否引用了图片
    if reply_message_id != -1:
        from function.group_operation import get_reply_image_url

        image_url = get_reply_image_url(reply_message_id)
        if image_url:
            from function.image_processor import getImagePathByFile

            try:
                file_name = f"reply_{message_id}_{uuid.uuid4().hex[:8]}.image"
                raw_reply_image_path = getImagePathByFile(file_name, image_url)
                temp_image_paths.append(raw_reply_image_path)
                image_path = await asyncio.to_thread(
                    normalize_image_for_ollama, raw_reply_image_path
                )
                if image_path:
                    temp_image_paths.append(image_path)
                    logging.info(f"检测到引用图片,已下载: {image_path}")
                else:
                    logging.error(f"引用图片无法转换为模型可读格式: {raw_reply_image_path}")
            except Exception as e:
                logging.error(f"下载引用图片失败: {e}")
                image_path = None

    # 初始化智能模块
    try:
        from intelligence.profile.profile_manager_async import (
            get_or_create_profile,
            update_profile,
        )
        from intelligence.context.context_manager_async import get_smart_context
        from intelligence.memory.memory_manager_async import retrieve_relevant_memories
        from intelligence.memory.smart_extractor import extract_and_store_memory_smart

        # 1. 获取用户画像 (异步)
        user_profile = await get_or_create_profile(user_id)

        # 2. 后台更新画像 (使用create_task而非threading)
        async def update_profile_background():
            try:
                # 添加超时保护
                await asyncio.wait_for(_update_profile_logic(), timeout=30.0)
            except asyncio.TimeoutError:
                logging.warning(f"[后台] 更新画像超时: user_id={user_id}")
            except Exception as e:
                logging.error(f"后台更新画像失败: {e}", exc_info=True)

        async def _update_profile_logic():
            """画像更新的实际逻辑"""
            from intelligence.profile.profile_extractor import ProfileExtractor

            profile_extractor = ProfileExtractor()

            logging.info(f"[后台] 开始更新画像: user_id={user_id}")
            features = profile_extractor.extract_from_message(text, user_id)
            updates = profile_extractor.merge_with_existing_profile(
                user_profile, features
            )

            if updates:
                await update_profile(user_id, updates)
                logging.info(f"[后台] 画像更新成功: {list(updates.keys())}")
            else:
                logging.info(f"[后台] 画像无需更新")

        create_tracked_task(update_profile_background())

        # 3. 智能上下文获取 (异步)
        context_result = await get_smart_context(
            user_id=user_id,
            group_id=group_id,
            user_profile=user_profile,
            current_message=text,
        )

        # 4. 检索相关记忆 (异步)
        relevant_memories = await retrieve_relevant_memories(
            user_id=user_id, current_message=text, limit=5
        )

        # 5. 智能提取新记忆 (后台任务，带过滤)
        async def extract_memory_background():
            try:
                # 添加超时保护
                await asyncio.wait_for(_extract_memory_logic(), timeout=20.0)
            except asyncio.TimeoutError:
                logging.warning(f"[后台] 提取记忆超时: user_id={user_id}")
            except Exception as e:
                logging.error(f"后台提取记忆失败: {e}", exc_info=True)

        async def _extract_memory_logic():
            """记忆提取的实际逻辑"""
            # 只提取有价值的记忆
            result = await extract_and_store_memory_smart(
                user_id=user_id,
                message=text,
                context_type="group",
                context_id=group_id,
            )
            logging.info(f"[后台] 记忆提取结果: {result}")

        # 只在消息较长时才提取记忆
        if len(text) > 10:
            create_tracked_task(extract_memory_background())

        # 6. 生成对话摘要 (后台任务，长对话时触发)
        async def generate_summary_background():
            try:
                # 添加超时保护
                await asyncio.wait_for(_generate_summary_logic(), timeout=30.0)
            except asyncio.TimeoutError:
                logging.warning(f"[后台] 生成摘要超时: user_id={user_id}")
            except Exception as e:
                logging.error(f"后台生成摘要失败: {e}", exc_info=True)

        async def _generate_summary_logic():
            """摘要生成的实际逻辑"""
            from intelligence.context.summary_generator_async import generate_summary

            msg_count = len(context_result.get("messages", []))
            logging.info(
                f"[后台] 检查摘要生成: user_id={user_id}, msg_count={msg_count}"
            )

            if msg_count >= 8:
                summary = await generate_summary(
                    user_id=user_id,
                    group_id=group_id,
                    messages=context_result["messages"],
                )
                logging.info(f"[后台] 摘要生成结果: {summary}")
            else:
                logging.info(f"[后台] 消息数不足8条,跳过摘要生成")

        create_tracked_task(generate_summary_background())

        # 7. 构建个性化system prompt
        from intelligence.personalization.prompt_builder import PromptBuilder

        prompt_builder = PromptBuilder()
        system_prompt = prompt_builder.build_personalized_prompt(
            base_prompt=getPrompts(),
            user_profile=user_profile,
            memories=relevant_memories,
            context_summary=context_result.get("summary"),
            current_user_name=sender_nickname,
        )

        # 8. 构建消息列表
        messages: list[dict[str, object]] = [
            {"role": "system", "content": system_prompt}
        ]
        messages.append({"role": "system", "content": target_user_guard})
        messages.append({"role": "system", "content": reply_style_guard})

        # 添加智能上下文消息
        if context_result["messages"]:
            messages.extend(
                await build_context_messages_for_model(
                    context_result["messages"],
                    message_id,
                    temp_image_paths,
                    direct_image_context,
                )
            )

        # 增加用户熟悉度 (后台任务)
        async def increment_familiarity_background():
            try:
                # 添加超时保护
                await asyncio.wait_for(
                    increment_familiarity(user_id, delta=0.01), timeout=10.0
                )
            except asyncio.TimeoutError:
                logging.warning(f"[后台] 增加熟悉度超时: user_id={user_id}")
            except Exception as e:
                logging.error(f"增加熟悉度失败: {e}")

        create_tracked_task(increment_familiarity_background())

    except Exception as e:
        # 如果智能模块出错,回退到原有逻辑
        logging.error(f"智能模块执行失败,回退到原有逻辑: {e}", exc_info=True)

        # 获取上下文消息 (异步版本)
        context_messages = await GetChatContext(user_id, group_id)

        # 构建基础消息结构
        messages: list[dict[str, object]] = [
            {
                "role": "system",
                "content": getPrompts(),
            }
        ]
        messages.append({"role": "system", "content": target_user_guard})
        messages.append({"role": "system", "content": reply_style_guard})

        # 添加上下文消息
        if context_messages:
            messages.extend(
                await build_context_messages_for_model(
                    context_messages,
                    message_id,
                    temp_image_paths,
                    direct_image_context,
                )
            )

    # 如果有图片,使用视觉模型
    user_content = f"[{sender_nickname}]: {text}" if sender_nickname else text
    current_image_paths: list[str] = []
    if direct_image_context:
        current_image_paths.extend(
            await download_images_from_segments(
                image_segments_from_message(raw_message),
                message_id,
                "current",
                temp_image_paths,
                DIRECT_CONTEXT_IMAGE_LIMIT,
            )
        )

    if image_path:
        current_image_paths.append(image_path)

    if current_image_paths:
        model = load_image_ai_model()
        thinking = load_image_ai_thinking()
        messages.append(
            {"role": "user", "content": user_content, "images": current_image_paths}
        )
    else:
        messages.append({"role": "user", "content": user_content})

    def cleanup_temp_images():
        for temp_image_path in dict.fromkeys(temp_image_paths):
            if temp_image_path and os.path.exists(temp_image_path):
                try:
                    os.remove(temp_image_path)
                    logging.info(f"已删除临时图片文件: {temp_image_path}")
                except Exception as e:
                    logging.error(f"删除临时图片文件失败: {temp_image_path}, error={e}")

    try:
        if load_setting("use_local_ai", True):
            # 使用线程池执行ollama调用，避免阻塞事件循环
            from ollama import chat

            print(f"使用模型: {model}")
            logging.info(f"使用模型: {model}")

            # 在线程池中运行同步的ollama调用
            def _call_ollama(chat_messages):
                return chat(
                    model=model,
                    messages=chat_messages,
                    options={
                        "temperature": 0.2,
                        "num_predict": response_token_limit,
                    },
                    think=thinking,
                )

            # 使用wait_for添加超时保护
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(_call_ollama, messages),
                    timeout=60.0,  # 60秒超时
                )
            except asyncio.TimeoutError:
                logging.error(f"Ollama调用超时 (群: {group_id})")
                cleanup_temp_images()
                return
            except Exception as image_error:
                if any(message.get("images") for message in messages):
                    logging.error(
                        f"带图片调用AI失败,降级为纯文本重试: {image_error}"
                    )
                    try:
                        response = await asyncio.wait_for(
                            asyncio.to_thread(
                                _call_ollama, remove_images_from_messages(messages)
                            ),
                            timeout=60.0,
                        )
                    except asyncio.TimeoutError:
                        logging.error(f"Ollama纯文本重试超时 (群: {group_id})")
                        cleanup_temp_images()
                        return
                else:
                    raise

            logging.info(
                "(AI)乐可在{}({})说:{}".format(
                    await GetGroupName(group_id),
                    group_id,
                    response["message"]["content"],
                )
            )

            content = response["message"]["content"]
            re_text = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()

            # 检查响应是否为空
            if not re_text:
                logging.warning(f"AI返回空响应，跳过回复 (群: {group_id})")
                cleanup_temp_images()
                return

        else:
            # OpenAI调用也使用线程池，避免阻塞
            from openai import OpenAI
            from openai.types.chat import ChatCompletionMessageParam

            open_ai_model = load_static_setting("open_ai_model", load_chat_ai_model())
            open_ai_thinking = load_static_setting(
                "ai_thinking", load_chat_ai_thinking()
            )
            print(f"使用模型: {open_ai_model}")
            logging.info(f"使用模型: {open_ai_model}")

            def _call_openai():
                client = OpenAI(
                    base_url=load_static_setting("open_ai_base_url", ""),
                    api_key=load_static_setting("open_ai_api_key", ""),
                )

                completion = client.chat.completions.create(
                    model=open_ai_model,
                    messages=cast(list[ChatCompletionMessageParam], messages),
                    temperature=0.2,
                    top_p=0.7,
                    max_tokens=response_token_limit,
                    extra_body=(
                        {
                            "chat_template_kwargs": {
                                "thinking": open_ai_thinking
                            }
                        }
                        if open_ai_thinking
                        else None
                    ),
                    stream=True,
                )

                think_content = ""
                re_text = ""
                for chunk in completion:
                    if not getattr(chunk, "choices", None):
                        continue
                    reasoning = getattr(
                        chunk.choices[0].delta, "reasoning_content", None
                    )
                    if reasoning:
                        think_content += reasoning
                    if chunk.choices and chunk.choices[0].delta.content is not None:
                        re_text = re_text + chunk.choices[0].delta.content

                return re_text

            # 使用wait_for添加超时保护
            try:
                re_text = await asyncio.wait_for(
                    asyncio.to_thread(_call_openai),
                    timeout=120.0,  # 120秒超时（OpenAI可能需要更长时间）
                )
            except asyncio.TimeoutError:
                logging.error(f"OpenAI调用超时 (群: {group_id})")
                cleanup_temp_images()
                return

            # 检查响应是否为空
            if not re_text:
                logging.warning(f"AI返回空响应，跳过回复 (群: {group_id})")
                cleanup_temp_images()
                return

            logging.info(
                "(AI)乐可在{}({})说:{}".format(
                    await GetGroupName(group_id), group_id, re_text
                )
            )

    except Exception as e:
        logging.error(f"调用AI时出错: {str(e)}")
        re_text = "呜呜不太理解呢喵."

    # 清理回复中的换行符
    while "\n" in re_text:
        re_text = re_text.replace("\n", "")

    # 删除临时图片
    cleanup_temp_images()

    await ReplySay(websocket, group_id, message_id, re_text)


# 辅助函数
async def increment_familiarity(user_id: int, delta: float = 0.05) -> bool:
    """增加用户熟悉度 (异步版本)"""
    import json
    from datetime import datetime
    from database.db_pool import intel_db_pool

    try:
        async with intel_db_pool.acquire() as conn:
            # 获取当前熟悉度
            cursor = await conn.execute(
                "SELECT familiarity_level FROM user_profile WHERE user_id = ?",
                (user_id,),
            )
            result = await cursor.fetchone()

            if result:
                current = result[0]
                new_value = min(1.0, current + delta)

                await conn.execute(
                    "UPDATE user_profile SET familiarity_level = ?, updated_at = ? WHERE user_id = ?",
                    (new_value, int(datetime.now().timestamp()), user_id),
                )
                await conn.commit()

                logging.info(
                    f"增加熟悉度: user_id={user_id}, {current:.2f} -> {new_value:.2f}"
                )
                return True

        return False

    except Exception as e:
        logging.error(f"增加熟悉度失败: {e}")
        return False


class GroupChatApplication(GroupMessageApplication):
    """群聊AI对话应用"""

    def __init__(self):
        applicationInfo = ApplicationInfo("ai聊天功能", "ai根据上下文聊天回复")
        if load_setting("use_local_ai", True):
            super().__init__(
                applicationInfo, 0, True, ApplicationCostType.HIGH_TIME_HIGH_PERFORMANCE
            )
        else:
            super().__init__(applicationInfo, 0, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        await chat(
            message.websocket,
            message.senderId,
            message.groupId,
            message.messageId,
            message.plainTextMessage,
            message.replyMessageId,
            getattr(message, "senderNickname", ""),
            message.rawMessage,
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发AI回复
        触发条件:
        1. 群聊开启了聊天功能
        2. 消息包含机器人名字
        3. 随机0.5%概率
        4. @机器人
        """
        if not get_config("enable_chat", message.groupId):
            return False
        if (
            (
                load_setting("bot_name", "乐可") in message.plainTextMessage
                or load_setting("bot_id", 0) in message.atList
            )
            and get_config("replay_chat", message.groupId)
        ) or (random.random() < 0.005 and get_config("random_chat", message.groupId)):
            return True
        return False
