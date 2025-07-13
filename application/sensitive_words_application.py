from data.message.group_message_info import GroupMessageInfo
from data.application.application_info import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from data.enumerates import ApplicationCostType

from function.say import SayGroup, ReplySay
from function.datebase_user import IsAdmin
from function.GroupConfig import get_config
from function.group_operation import ban_new, delete_msg


class SensitiveWordsApplication(GroupMessageApplication):

    async def process(self, message: GroupMessageInfo):
        """处理消息

        Args:
            message (MessageInfo): 要处理的消息
        """
        await ReplySay(
            message.websocket,
            message.groupId,
            message.messageId,
            f"触发本群违禁词规则喵，禁言{get_config("sensitive_ban_sec", message.groupId)}秒喵！",
        )
        await ban_new(
            message.websocket,
            message.senderId,
            message.groupId,
            get_config("sensitive_ban_sec", message.groupId),  # type: ignore
        )
        if get_config("sensitive_withdrawn", message.groupId):
            await delete_msg(message.websocket, message.messageId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否成立

        Args:
            message (MessageInfo): 传入消息

        Returns:
            bool: 判断结果
        """
        for i in get_config("sensitive_words", message.groupId):  # type: ignore
            if i in message.plainTextMessage and i not in "[图片]@":
                return True
        return False

    def __init__(self):
        applicationInfo = ApplicationInfo("敏感词检查", "出现敏感词就禁言")
        super().__init__(applicationInfo, 65, True, ApplicationCostType.NORMAL)
