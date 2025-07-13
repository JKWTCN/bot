from data.message.group_message_info import GroupMessageInfo
from data.application.application_info import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from data.enumerates import ApplicationCostType

from function.say import SayGroup, ReplySay
from function.datebase_user import IsAdmin
from function.GroupConfig import manage_config, GroupConfigError


class GroupConfigApplication(GroupMessageApplication):

    async def process(self, message: GroupMessageInfo):
        """处理消息

        Args:
            message (MessageInfo): 要处理的消息
        """
        argStatus, newArg = manage_config(
            message.plainTextMessage, message.groupId  # type: ignore
        )
        if argStatus:
            await SayGroup(
                message.websocket,
                message.groupId,
                f"操作成功喵,当前该参数的值为:{newArg}",
            )
        else:

            match newArg:
                case GroupConfigError.NO_OPPATION_Type:
                    text = "设置失败喵,设置名称错误喵。"
                case GroupConfigError.UNKNOW_DATA_TYPE:
                    text = "设置失败喵,数据类型错误喵。"
                case GroupConfigError.UNKNOW_OPPATION_ARG:
                    text = "设置失败喵,操作类型错误喵。"
            await ReplySay(
                message.websocket,
                message.groupId,
                message.messageId,
                text,
            )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否成立

        Args:
            message (MessageInfo): 传入消息

        Returns:
            bool: 判断结果
        """
        return message.plainTextMessage.startswith(".") and IsAdmin(
            message.senderId, message.groupId
        )

    def __init__(self):
        applicationInfo = ApplicationInfo("测试应用", "测试功能")
        super().__init__(applicationInfo, 65, True, ApplicationCostType.NORMAL)
