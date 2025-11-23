import time
from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.GroupConfig import get_config
from function.say import ReplySay
from function.database_message import get_md5_info
from function.datebase_user import IsAdmin, get_user_name


class RepeatMachineApplication(GroupMessageApplication):
    def __init__(
        self,
    ):
        applicationInfo = ApplicationInfo("复读机", "检测群友复读机行为")
        super().__init__(applicationInfo, 100, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        all_count, user_count, last_msg_id, last_msg_time = get_md5_info(
            message.senderId, message.groupId, message.readMessage
        )
        if all_count >= 2 and user_count >= 1:
            timeArray = time.localtime(last_msg_time)
            otherStyleTime = time.strftime("%Y-%m-%d %H:%M:%S", timeArray)
            sender_name = get_user_name(message.senderId, message.groupId)
            await ReplySay(
                message.websocket,
                message.groupId,
                int(last_msg_id),  # type: ignore
                f"{sender_name},该消息最后出现在这里:{otherStyleTime}喵,这是本群第{all_count + 1}次复读喵,是你本人第{user_count + 1}次复读喵。",
            )

    def judge(self, message: GroupMessageInfo) -> bool:
        if get_config("repeat_check", message.groupId) and message.isPainTextMessage:
            return True
        return False
