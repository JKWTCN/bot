import logging
import random
import re

import requests

from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.say import SayRaw, ReplySay
from function.database_message import GetChatContext
from function.database_group import GetGroupName
from tools.tools import load_setting


async def chat(websocket, user_id: int, group_id: int, message_id: int, text: str):
    """ai聊天功能回复
    Args:
        websocket (_type_): 回复的websocket
        user_id (int): 用户的id
        group_id (int): 群的id
        message_id (int): 消息id
        text (str): 传入信息,在ai回复后追加在后面
    """
    port = "11434"
    url = f"http://localhost:{port}/api/chat"
    model = "qwen3:8b"  # 模型名称
    headers = {"Content-Type": "application/json"}

    # 获取上下文消息
    context_messages = GetChatContext(user_id, group_id)

    # 构建基础消息结构
    base_messages = [
        {
            "role": "system",
            "content": "你叫乐可,现在你将模仿一只傲娇并且温柔的猫娘(猫娘是一种拟人化的生物,其行为似猫但类人.),与我对话每一句话后面都要加上'喵'",
        }
    ]

    # 添加上下文消息
    if context_messages:
        base_messages.extend(context_messages)

    data = {
        "model": model,
        "options": {"temperature": 1.0},
        "stream": False,
        "messages": base_messages,
    }

    # 特殊模型处理
    if model == "qwen3:8b":
        for msg in data["messages"]:
            if msg["role"] == "system":
                msg["content"] = "/nothink " + msg["content"]
            elif msg["role"] == "user":
                msg["content"] = "/nothink " + msg["content"]

    try:
        print(data)
        response = requests.post(url, json=data, headers=headers, timeout=300)
        res = response.json()

        # 记录日志
        logging.info(
            "(AI)乐可在{}({})说:{}".format(
                GetGroupName(group_id), group_id, res["message"]["content"]
            )
        )

        if model != "deepseek-r1:1.5b" and model != "qwen3:8b":
            re_text = res["message"]["content"]
        else:
            match = re.findall(
                r"<think>([\s\S]*)</think>([\s\S]*)",
                res["message"]["content"],
            )
            re_text = match[0][1]
    except:
        logging.info("连接超时")
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
        ):
            return True
        return False
