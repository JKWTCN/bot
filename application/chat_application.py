import json
import logging
import random
import re
import string

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


async def chat(websocket, user_id: int, group_id: int, message_id: int, text: str):
    """ai聊天功能回复
    Args:
        websocket (_type_): 回复的websocket
        user_id (int): 用户的id
        group_id (int): 群的id
        message_id (int): 消息id
        text (str): 传入信息,在ai回复后追加在后面
    """
    model = "qwen3:8b"  # 模型名称

    # 获取上下文消息
    context_messages = GetChatContext(user_id, group_id)

    # 构建基础消息结构
    base_messages = [
        {
            "role": "system",
            "content": getPrompts(),
        }
    ]

    # 添加上下文消息
    if context_messages:
        base_messages.extend(context_messages)

    try:
        import ollama

        print(f"使用模型: {model}, 消息: {base_messages}")
        logging.info(f"使用模型: {model}, 消息: {base_messages}")
        response = ollama.chat(
            model=model,
            messages=base_messages,
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
            match = re.findall(
                r"<think>([\s\S]*)</think>([\s\S]*)",
                response['message']['content'],
            )
            if match:
                re_text = match[0][1]
            else:
                re_text = response['message']['content'].strip()
    except Exception as e:
        logging.error(f"调用Ollama时出错: {str(e)}")
        re_text = "呜呜不太理解呢喵."

    # 清理回复中的换行符
    while "\n" in re_text:
        re_text = re_text.replace("\n", "")

    if text != "":
        re_text += "\n\n" + text
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
            message.websocket, message.senderId, message.groupId, message.messageId, ""
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
