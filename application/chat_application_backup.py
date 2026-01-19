import asyncio
import json
import logging
import os
import random
import re
import string
import threading
import uuid

import requests
from typing import cast

from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.say import SayRaw, ReplySay
from function.database_message import GetChatContext
from function.database_group import GetGroupName
from tools.tools import load_setting, load_static_setting

from tools.tools import GetNCWCPort, GetNCHSPort, GetOllamaPort


def getPrompts() -> str:
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

        # 2. 提取特征并更新画像(后台线程,不阻塞)
        def update_profile_thread():
            try:
                logging.info(f"[后台] 开始更新画像: user_id={user_id}")
                features = profile_extractor.extract_from_message(text, user_id)
                updates = profile_extractor.merge_with_existing_profile(
                    user_profile, features
                )
                if updates:
                    profile_manager.update_profile(user_id, updates)
                    logging.info(f"[后台] 画像更新成功: {list(updates.keys())}")
                else:
                    logging.info(f"[后台] 画像无需更新")
            except Exception as e:
                logging.error(f"后台更新画像失败: {e}", exc_info=True)

        threading.Thread(target=update_profile_thread, daemon=True).start()

        # 3. 智能上下文获取
        context_result = await context_manager.get_smart_context(
            user_id=user_id,
            group_id=group_id,
            user_profile=user_profile,
            current_message=text,
        )

        # 4. 检索相关记忆
        relevant_memories = memory_manager.retrieve_relevant_memories(
            user_id=user_id, current_message=text, limit=5
        )

        # 5. 提取新记忆(后台线程)
        def extract_memory_thread():
            try:
                logging.info(
                    f"[后台] 开始提取记忆: user_id={user_id}, text={text[:30]}"
                )
                result = memory_manager.extract_and_store_memory(
                    user_id=user_id,
                    message=text,
                    context_type="group",
                    context_id=group_id,
                )
                logging.info(f"[后台] 记忆提取结果: {result}")
            except Exception as e:
                logging.error(f"后台提取记忆失败: {e}", exc_info=True)

        threading.Thread(target=extract_memory_thread, daemon=True).start()

        # 6. 生成对话摘要(后台线程,只在长对话时触发)
        def generate_summary_thread():
            try:
                msg_count = len(context_result.get("messages", []))
                logging.info(
                    f"[后台] 检查摘要生成: user_id={user_id}, msg_count={msg_count}"
                )
                if msg_count >= 8:
                    summary = summary_generator.generate_summary(
                        user_id=user_id,
                        group_id=group_id,
                        messages=context_result["messages"],
                    )
                    logging.info(f"[后台] 摘要生成结果: {summary}")
                else:
                    logging.info(f"[后台] 消息数不足8条,跳过摘要生成")
            except Exception as e:
                logging.error(f"后台生成摘要失败: {e}", exc_info=True)

        threading.Thread(target=generate_summary_thread, daemon=True).start()

        # 7. 构建个性化system prompt
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
        if load_setting("use_local_ai", True):
            import ollama

            print(f"使用模型: {model}, 消息: {messages}")
            logging.info(f"使用模型: {model}, 消息: {messages}")
            response = ollama.chat(
                model=model, messages=messages, options={"temperature": 0.2}
            )
                    # 记录日志
            logging.info(
                "(AI)乐可在{}({})说:{}".format(
                    GetGroupName(group_id), group_id, response["message"]["content"]
                )
            )

            if model != "deepseek-r1:1.5b" and model != "qwen3:8b":
                re_text = response["message"]["content"]
            else:
                # 对于需要思考的模型，需要提取最终回答（去除思考过程）
                content = response["message"]["content"]

                # 用正则匹配并去除思考内容（匹配 <think> 标签包裹的内容）
                re_text = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
        else:
            from openai import OpenAI
            from openai.types.chat import ChatCompletionMessageParam
            client = OpenAI(
                base_url=load_static_setting("open_ai_base_url", ""),
                api_key=load_static_setting("open_ai_api_key", ""),
            )
            print(f"使用模型: {load_static_setting("open_ai_model", "")}, 消息: {messages}")
            logging.info(f"使用模型: {load_static_setting("open_ai_model", "")}, 消息: {messages}")
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
                    think_content+=reasoning
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    re_text= re_text + chunk.choices[0].delta.content
            logging.info(
                "(AI)乐可在{}({})说:{}".format(
                    GetGroupName(group_id), group_id, re_text
                )
            )
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
        """百分之5概率触发回复或者带名字回复"""
        if (
            load_setting("bot_name", "乐可") in message.plainTextMessage
            or random.random() < 0.05
            or load_setting("bot_id", 0) in message.atList
        ):
            return True
        return False
