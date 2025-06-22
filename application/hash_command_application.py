from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMesssageInfo
from function.say import SayRaw
import random
from function.database_message import getImageInfo
from function.group_operation import replyImageMessage


class HashCommandApplication(GroupMessageApplication):
    def __init__(
        self,
    ):
        applicationInfo = ApplicationInfo(
            "#指令", "测试指令:#image#对图片进行评论;#info#获取图片信息;"
        )
        super().__init__(applicationInfo, 100, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMesssageInfo):
        if "#image#" in message.painTextMessage:
            now_text = message.painTextMessage.replace("#image#", "")
            await replyImageMessage(
                message.websocket,
                message.groupId,
                message.replyMessageId,
                message.messageId,
                "",
            )
        elif "#info#" in message.painTextMessage:
            await getImageInfo(
                message.websocket,
                message.groupId,
                message.replyMessageId,
                message.messageId,
            )

    def judge(self, message: GroupMesssageInfo) -> bool:
        """"""
        return (
            "#image#" in message.painTextMessage or "#info#" in message.painTextMessage
        )
