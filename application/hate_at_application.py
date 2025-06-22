from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMesssageInfo
from function.say import SayRaw
from function.GroupConfig import get_config
from function.database_message import getWhoAtMe, incWhoAtMe
from function.datebase_user import BotIsAdmin, IsAdmin, get_user_name
from function.group_operation import banNormal, ReplySayGroup
import random


class HateAtApplicaiton(GroupMessageApplication):
    def __init__(
        self,
    ):
        applicationInfo = ApplicationInfo(
            "艾特提醒", "如果你不想被艾特可以让乐可提醒艾特你的人"
        )
        super().__init__(applicationInfo, 75, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMesssageInfo):
        user_id = message.senderId
        group_id = message.groupId
        websocket = message.websocket
        message_id = message.messageId
        at_ids = set(message.atList) & set(get_config("hate_at_list", message.groupId))  # type: ignore
        for at_id in at_ids:
            incWhoAtMe(message.senderId, at_id)
            nowAtNums = getWhoAtMe(message.senderId, at_id)
            if BotIsAdmin(group_id) and not IsAdmin(user_id, group_id):
                if nowAtNums > 3:
                    await banNormal(websocket, user_id, group_id, 60 * nowAtNums)
                    await ReplySayGroup(
                        websocket,
                        group_id,
                        message_id,
                        f"{get_user_name(user_id,group_id)},你是第{nowAtNums}次艾特{get_user_name(at_id,group_id)}了喵,{get_user_name(at_id,group_id)}不喜欢被艾特喵，禁言你{nowAtNums}分钟了喵，引用记得删除艾特喵。",
                    )
                else:
                    await ReplySayGroup(
                        websocket,
                        group_id,
                        message_id,
                        f"{get_user_name(user_id,group_id)},你是第{nowAtNums}次艾特{get_user_name(at_id,group_id)}了喵,{get_user_name(at_id,group_id)}不喜欢被艾特喵，事不过三喵,你还有{3-nowAtNums}次机会喵，引用记得删除艾特喵。",
                    )
            else:
                await ReplySayGroup(
                    websocket,
                    group_id,
                    message_id,
                    f"{get_user_name(user_id,group_id)},你是第{nowAtNums}次艾特{get_user_name(at_id,group_id)}了喵,{get_user_name(at_id,group_id)}不喜欢被艾特喵，引用记得删除艾特喵。",
                )

    def judge(self, message: GroupMesssageInfo) -> bool:
        """艾特提醒"""
        return bool(set(message.atList) & set(get_config("hate_at_list", message.groupId)))  # type: ignore
