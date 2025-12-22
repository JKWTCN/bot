import logging
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

from tools.tools import GetNCWCPort, GetNCHSPort, GetOllamaPort


async def miaomiaoTranslation(websocket, user_id: int, group_id: int, message_id: int):
    """喵喵翻译功能

    Args:
        websocket (_type_): _description_
        user_id (int): _description_
        group_id (int): _description_
        message_id (int): _description_
    """
    model = "qwen3-vl:8b"

    # 获取上下文消息
    context_messages = GetChatContext(user_id, group_id)

    # 构建基础消息结构
    from application.chat_application import getPrompts

    base_messages = [
        {
            "role": "system",
            "content": getPrompts(),
        }
    ]

    # 添加上下文消息
    if context_messages:
        base_messages.extend(context_messages)
    base_messages.append(
        {
            "role": "user",
            "content": "这是你的同类,但是它有点笨,它只会说喵,帮它翻译一下子它说的最后一句喵喵组成的话,谢谢。",
        }
    )

    try:
        import ollama

        print(f"使用模型: {model}, 消息: {base_messages}")
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

    re_text += (
        "\n\n"
        + "这是乐可的猫娘同类喵,它有点傻傻的,只会说喵,这是乐可帮它翻译的喵,请不要欺负它喵。"
    )
    await ReplySay(websocket, group_id, message_id, re_text)


from tools.tools import HasChinese


def CheckAllMiao(text):
    """
    检查给定文本中的字符除标点符号外的字符是否都是"喵"
    """
    if len(text) == 0:
        return False
    # 遍历文本中的每个字符
    # 获取所有标点符号
    punctuations = string.punctuation + "。，、；：「」『』（）【】《》？！…—"

    for char in text:
        # 如果字符不是标点符号且不是"喵"，返回False
        if char not in punctuations and char != "喵":
            return False
    # 所有非标点符号字符都是"喵"
    return True


class MiaoMiaoTranslationApplication(GroupMessageApplication):
    def __init__(
        self,
    ):
        applicationInfo = ApplicationInfo("猫猫翻译", "把群友全是喵喵的话翻译成中文。")
        super().__init__(
            applicationInfo, 75, True, ApplicationCostType.HIGH_TIME_HIGH_PERFORMANCE
        )

    async def process(self, message: GroupMessageInfo):
        # await SayRaw(message.websocket, message.groupId, message.rawMessage["message"])
        await miaomiaoTranslation(
            message.websocket, message.senderId, message.groupId, message.messageId
        )
        pass

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断消息是否符合喵喵翻译条件:纯文本,而且全部由喵组成。"""
        if (
            CheckAllMiao(message.plainTextMessage)
            and len(message.imageFileList) == 0
            and len(message.fileList) == 0
            and len(message.faceList) == 0
            and HasChinese(message.plainTextMessage)
        ):
            return True
        return False
