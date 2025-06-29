from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.say import SayRaw
import random


class ReReadApplication(GroupMessageApplication):
    def __init__(
        self,
    ):
        applicationInfo = ApplicationInfo("复读", "随机复读群友的话")
        super().__init__(applicationInfo, 100, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        await SayRaw(message.websocket, message.groupId, message.rawMessage["message"])

    def judge(self, message: GroupMessageInfo) -> bool:
        if random.random() < 0.01:
            return True
        else:
            return False
