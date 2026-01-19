import random
import sqlite3
from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.say import SayAndAt
from tools.tools import HasKeyWords, load_setting

# 导入线程池包装器，避免数据库锁定
from database.sync_wrapper import run_in_thread_sync


def get_group_member_list(group_id: int) -> list[int]:
    """获取群成员ID列表"""
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id FROM group_member_info WHERE group_id=?;",
        (group_id,),
    )
    data = cur.fetchall()
    conn.close()
    return [row[0] for row in data]


class AtRandomGroupFriendApplication(GroupMessageApplication):
    """艾特随机群友应用"""

    def __init__(self):
        applicationInfo = ApplicationInfo("艾特随机群友", "随机艾特一个群友")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        """处理消息"""
        group_id = message.groupId
        websocket = message.websocket

        # 获取群成员列表
        member_list = get_group_member_list(group_id)

        if not member_list:
            await SayAndAt(
                websocket, message.senderId, group_id, "获取不到群成员列表了喵..."
            )
            return

        # 随机选择一个成员
        random_member_id = random.choice(member_list)

        # 获取发送者名称
        from function.datebase_user import get_user_name

        sender_name = get_user_name(message.senderId, group_id)
        member_name = get_user_name(random_member_id, group_id)

        # 发送艾特消息
        await SayAndAt(
            websocket, random_member_id, group_id, f"{member_name} 被{sender_name}抽中了喵！"
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断消息是否符合触发条件"""
        return (
            HasKeyWords(
                message.plainTextMessage, ["艾特随机群友", "随机艾特", "艾特随机","随机群友"]
            )
            and load_setting("bot_name", "乐可") in message.plainTextMessage
        )
