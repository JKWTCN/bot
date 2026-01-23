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
from typing import cast

import requests

from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.say import SayRaw, ReplySay
from function.database_message_async import GetChatContext
from function.database_group_async import GetGroupName
from tools.tools import load_setting, load_static_setting

from tools.tools import GetNCWCPort, GetNCHSPort, GetOllamaPort


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
    model = "qwen3:8b"
    image_path = None

    # 检查是否引用了图片
    if reply_message_id != -1:
        from function.group_operation import get_reply_image_url

        image_url = get_reply_image_url(reply_message_id)
        if image_url:
            from function.image_processor import getImagePathByFile

            try:
                file_name = f"reply_{message_id}_{uuid.uuid4().hex[:8]}.image"
                image_path = getImagePathByFile(file_name, image_url)
                logging.info(f"检测到引用图片,已下载: {image_path}")
            except Exception as e:
                logging.error(f"下载引用图片失败: {e}")
                image_path = None

    # 初始化智能模块
    try:
        from intelligence.profile.profile_manager_async import get_or_create_profile, update_profile
        from intelligence.context.context_manager_async import get_smart_context
        from intelligence.memory.memory_manager_async import retrieve_relevant_memories
        from intelligence.memory.smart_extractor import extract_and_store_memory_smart

        # 1. 获取用户画像 (异步)
        user_profile = await get_or_create_profile(user_id)

        # 2. 后台更新画像 (使用create_task而非threading)
        async def update_profile_background():
            try:
                from intelligence.profile.profile_extractor import ProfileExtractor
                profile_extractor = ProfileExtractor()

                logging.info(f"[后台] 开始更新画像: user_id={user_id}")
                features = profile_extractor.extract_from_message(text, user_id)
                updates = profile_extractor.merge_with_existing_profile(user_profile, features)

                if updates:
                    await update_profile(user_id, updates)
                    logging.info(f"[后台] 画像更新成功: {list(updates.keys())}")
                else:
                    logging.info(f"[后台] 画像无需更新")
            except Exception as e:
                logging.error(f"后台更新画像失败: {e}", exc_info=True)

        asyncio.create_task(update_profile_background())

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
                # 只提取有价值的记忆
                result = await extract_and_store_memory_smart(
                    user_id=user_id,
                    message=text,
                    context_type="group",
                    context_id=group_id,
                )
                logging.info(f"[后台] 记忆提取结果: {result}")
            except Exception as e:
                logging.error(f"后台提取记忆失败: {e}", exc_info=True)

        # 只在消息较长时才提取记忆
        if len(text) > 10:
            asyncio.create_task(extract_memory_background())

        # 6. 生成对话摘要 (后台任务，长对话时触发)
        async def generate_summary_background():
            try:
                from intelligence.context.summary_generator_async import generate_summary

                msg_count = len(context_result.get("messages", []))
                logging.info(f"[后台] 检查摘要生成: user_id={user_id}, msg_count={msg_count}")

                if msg_count >= 8:
                    summary = await generate_summary(
                        user_id=user_id,
                        group_id=group_id,
                        messages=context_result["messages"],
                    )
                    logging.info(f"[后台] 摘要生成结果: {summary}")
                else:
                    logging.info(f"[后台] 消息数不足8条,跳过摘要生成")
            except Exception as e:
                logging.error(f"后台生成摘要失败: {e}", exc_info=True)

        asyncio.create_task(generate_summary_background())

        # 7. 构建个性化system prompt
        from intelligence.personalization.prompt_builder import PromptBuilder

        prompt_builder = PromptBuilder()
        system_prompt = prompt_builder.build_personalized_prompt(
            base_prompt=getPrompts(),
            user_profile=user_profile,
            memories=relevant_memories,
            context_summary=context_result.get("summary"),
        )

        # 8. 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]

        # 添加智能上下文消息
        if context_result["messages"]:
            messages.extend(context_result["messages"])

        # 增加用户熟悉度 (后台任务)
        async def increment_familiarity_background():
            try:
                await increment_familiarity(user_id, delta=0.01)
            except Exception as e:
                logging.error(f"增加熟悉度失败: {e}")

        asyncio.create_task(increment_familiarity_background())

    except Exception as e:
        # 如果智能模块出错,回退到原有逻辑
        logging.error(f"智能模块执行失败,回退到原有逻辑: {e}", exc_info=True)

        # 获取上下文消息 (异步版本)
        context_messages = await GetChatContext(user_id, group_id)

        # 构建基础消息结构
        messages = [
            {
                "role": "system",
                "content": getPrompts(),
            }
        ]

        # 添加上下文消息
        if context_messages:
            messages.extend(context_messages)

    # 如果有图片,使用视觉模型
    if image_path:
        model = "qwen3-vl:8b"
        messages.append({"role": "user", "content": text, "images": [image_path]})
    else:
        messages.append({"role": "user", "content": text})

    try:
        if load_setting("use_local_ai", True):
            # 使用线程池执行ollama调用，避免阻塞事件循环
            import ollama

            print(f"使用模型: {model}")
            logging.info(f"使用模型: {model}")

            # 在线程池中运行同步的ollama调用
            def _call_ollama():
                return ollama.chat(
                    model=model, messages=messages, options={"temperature": 0.2}
                )

            response = await asyncio.to_thread(_call_ollama)

            logging.info(
                "(AI)乐可在{}({})说:{}".format(
                    await GetGroupName(group_id), group_id, response["message"]["content"]
                )
            )

            if model != "deepseek-r1:1.5b" and model != "qwen3:8b":
                re_text = response["message"]["content"]
            else:
                content = response["message"]["content"]
                re_text = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()

            # 检查响应是否为空
            if not re_text:
                logging.warning(f"AI返回空响应，跳过回复 (群: {group_id})")
                return

        else:
            # OpenAI调用也使用线程池，避免阻塞
            from openai import OpenAI
            from openai.types.chat import ChatCompletionMessageParam

            print(f"使用模型: {load_static_setting('open_ai_model', '')}")
            logging.info(f"使用模型: {load_static_setting('open_ai_model', '')}")

            def _call_openai():
                client = OpenAI(
                    base_url=load_static_setting("open_ai_base_url", ""),
                    api_key=load_static_setting("open_ai_api_key", ""),
                )

                completion = client.chat.completions.create(
                    model=load_static_setting("open_ai_model", ""),
                    messages=cast(list[ChatCompletionMessageParam], messages),
                    temperature=0.2,
                    top_p=0.7,
                    max_tokens=8192,
                    extra_body={"chat_template_kwargs": {"thinking": True}},
                    stream=True,
                )

                think_content = ""
                re_text = ""
                for chunk in completion:
                    if not getattr(chunk, "choices", None):
                        continue
                    reasoning = getattr(chunk.choices[0].delta, "reasoning_content", None)
                    if reasoning:
                        think_content += reasoning
                    if chunk.choices and chunk.choices[0].delta.content is not None:
                        re_text = re_text + chunk.choices[0].delta.content

                return re_text

            re_text = await asyncio.to_thread(_call_openai)

            # 检查响应是否为空
            if not re_text:
                logging.warning(f"AI返回空响应，跳过回复 (群: {group_id})")
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
    if image_path and os.path.exists(image_path):
        os.remove(image_path)
        logging.info(f"已删除临时图片文件: {image_path}")

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
                (user_id,)
            )
            result = await cursor.fetchone()

            if result:
                current = result[0]
                new_value = min(1.0, current + delta)

                await conn.execute(
                    "UPDATE user_profile SET familiarity_level = ?, updated_at = ? WHERE user_id = ?",
                    (new_value, int(datetime.now().timestamp()), user_id)
                )
                await conn.commit()

                logging.info(f"增加熟悉度: user_id={user_id}, {current:.2f} -> {new_value:.2f}")
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
            super().__init__(
                applicationInfo, 0, True, ApplicationCostType.NORMAL
            )

    async def process(self, message: GroupMessageInfo):
        await chat(
            message.websocket,
            message.senderId,
            message.groupId,
            message.messageId,
            message.plainTextMessage,
            message.replyMessageId,
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发AI回复
        触发条件:
        1. 消息包含机器人名字
        2. 随机5%概率
        3. @机器人
        """
        if (
            load_setting("bot_name", "乐可") in message.plainTextMessage
            or random.random() < 0.05
            or load_setting("bot_id", 0) in message.atList
        ):
            return True
        return False
