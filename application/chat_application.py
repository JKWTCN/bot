import asyncio
import json
import logging
import os
import random
import re
import string
import uuid

import requests

from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.say import SayRaw, ReplySay
from function.database_message import GetChatContext
from function.database_group import GetGroupName
from tools.tools import load_setting

from tools.tools import GetNCWCPort, GetNCHSPort, GetOllamaPort


def getPrompts() -> str:
    with open("prompts.json", "r", encoding="utf-8") as f:
        prompts = json.load(f)
    return str(prompts)


async def chat(websocket, user_id: int, group_id: int, message_id: int, text: str, reply_message_id: int = -1):
    """ai聊天功能回复 (增强版 - 集成智能模块)
    Args:
        websocket (_type_): 回复的websocket
        user_id (int): 用户的id
        group_id (int): 群的id
        message_id (int): 消息id
        text (str): 传入信息,在ai回复后追加在后面
        reply_message_id (int): 引用的消息ID,如果有则检查是否包含图片
    """
    model = "qwen3:8b"  # 模型名称
    image_path = None

    # 检查是否引用了图片
    if reply_message_id != -1:
        from function.group_operation import get_reply_image_url
        image_url = get_reply_image_url(reply_message_id)
        if image_url:
            # 下载图片
            from function.image_processor import getImagePathByFile
            try:
                # 使用UUID生成唯一文件名
                file_name = f"reply_{message_id}_{uuid.uuid4().hex[:8]}.image"
                image_path = getImagePathByFile(file_name, image_url)
                logging.info(f"检测到引用图片,已下载: {image_path}")
            except Exception as e:
                logging.error(f"下载引用图片失败: {e}")
                image_path = None

    # 初始化智能模块 (新增)
    try:
        from intelligence.profile.profile_manager import ProfileManager
        from intelligence.profile.profile_extractor import ProfileExtractor
        from intelligence.context.context_manager import ContextManager
        from intelligence.context.summary_generator import SummaryGenerator
        from intelligence.personalization.prompt_builder import PromptBuilder
        from intelligence.memory.memory_manager import MemoryManager

        profile_manager = ProfileManager()
        profile_extractor = ProfileExtractor()
        context_manager = ContextManager()
        summary_generator = SummaryGenerator()
        prompt_builder = PromptBuilder()
        memory_manager = MemoryManager()

        # 1. 获取用户画像
        user_profile = profile_manager.get_or_create_profile(user_id)

        # 2. 提取特征并更新画像(异步,不阻塞)
        async def update_profile_async():
            try:
                features = profile_extractor.extract_from_message(text, user_id)
                updates = profile_extractor.merge_with_existing_profile(user_profile, features)
                if updates:
                    profile_manager.update_profile(user_id, updates)
            except Exception as e:
                logging.error(f"异步更新画像失败: {e}")

        asyncio.create_task(update_profile_async())

        # 3. 智能上下文获取
        context_result = await context_manager.get_smart_context(
            user_id=user_id,
            group_id=group_id,
            user_profile=user_profile,
            current_message=text
        )

        # 4. 检索相关记忆
        relevant_memories = memory_manager.retrieve_relevant_memories(
            user_id=user_id,
            current_message=text,
            limit=5
        )

        # 5. 提取新记忆(异步)
        async def extract_memory_async():
            try:
                memory_manager.extract_and_store_memory(
                    user_id=user_id,
                    message=text,
                    context_type="group",
                    context_id=group_id
                )
            except Exception as e:
                logging.error(f"异步提取记忆失败: {e}")

        asyncio.create_task(extract_memory_async())

        # 6. 生成对话摘要(异步,只在长对话时触发)
        async def generate_summary_async():
            try:
                if len(context_result.get('messages', [])) >= 8:
                    summary_generator.generate_summary(
                        user_id=user_id,
                        group_id=group_id,
                        messages=context_result['messages']
                    )
            except Exception as e:
                logging.error(f"异步生成摘要失败: {e}")

        asyncio.create_task(generate_summary_async())

        # 7. 构建个性化system prompt
        system_prompt = prompt_builder.build_personalized_prompt(
            base_prompt=getPrompts(),
            user_profile=user_profile,
            memories=relevant_memories,
            context_summary=context_result.get('summary')
        )

        # 8. 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]

        # 添加智能上下文消息
        if context_result['messages']:
            messages.extend(context_result['messages'])

        # 增加用户熟悉度
        profile_manager.increment_familiarity(user_id, delta=0.01)

    except Exception as e:
        # 如果智能模块出错,回退到原有逻辑
        logging.error(f"智能模块执行失败,回退到原有逻辑: {e}", exc_info=True)

        # 获取上下文消息 (原有逻辑)
        context_messages = GetChatContext(user_id, group_id)

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
        # 有图片时,包含图片信息
        messages.append({"role": "user", "content": text, "images": [image_path]})  # type: ignore
    else:
        # 没有图片时,只添加文本消息
        messages.append({"role": "user", "content": text})

    try:
        import ollama

        print(f"使用模型: {model}, 消息: {messages}")
        logging.info(f"使用模型: {model}, 消息: {messages}")
        response = ollama.chat(
            model=model,
            messages=messages,
            options={'temperature': 1.0}
        )

        # 记录日志
        logging.info(
            "(AI)乐可在{}({})说:{}".format(
                GetGroupName(group_id), group_id, response['message']['content']
            )
        )

        if model != "deepseek-r1:1.5b" and model != "qwen3:8b":
            re_text = response['message']['content']
        else:
            # 对于需要思考的模型，需要提取最终回答（去除思考过程）
            content = response['message']['content']

            # 用正则匹配并去除思考内容（匹配 <think> 标签包裹的内容）
            re_text = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
    except Exception as e:
        logging.error(f"调用Ollama时出错: {str(e)}")
        re_text = "呜呜不太理解呢喵."

    # 清理回复中的换行符
    while "\n" in re_text:
        re_text = re_text.replace("\n", "")

    # 删除临时图片
    if image_path and os.path.exists(image_path):
        os.remove(image_path)
        logging.info(f"已删除临时图片文件: {image_path}")

    await ReplySay(websocket, group_id, message_id, re_text)


class GroupChatApplication(GroupMessageApplication):
    def __init__(
        self,
    ):
        applicationInfo = ApplicationInfo("ai聊天功能", "ai根据上下文聊天回复")
        super().__init__(
            applicationInfo, 0, True, ApplicationCostType.HIGH_TIME_HIGH_PERFORMANCE
        )

    async def process(self, message: GroupMessageInfo):
        await chat(
            message.websocket, message.senderId, message.groupId, message.messageId, message.plainTextMessage, message.replyMessageId
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        """百分之5概率触发回复或者带名字回复"""
        if (
            load_setting("bot_name", "乐可") in message.plainTextMessage
            or random.random() < 0.05
            or load_setting("bot_id", 0) in message.atList
        ):
            return True
        return False
