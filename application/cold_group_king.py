import time
from data.application.group_message_application import GroupMessageApplication
from data.message.group_message_info import GroupMessageInfo
from data.application.meta_application import MetaMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType, MetaEventType
from data.message.meta_message_info import MetaMessageInfo
from function.say import SayRaw, SayGroup
import random
from function.database_message import getImageInfo
from function.group_operation import replyImageMessage
from function.group_setting import DumpGroupSetting, LoadGroupSetting
from tools.tools import load_setting, dump_setting
import sqlite3
import logging
from function.database_group import GetAllGroupId
from application.chat_application import chat

# 导入线程池包装器，避免数据库锁定
from database.sync_wrapper import run_in_thread_sync




# 设置冷群王次数
def SetColdGroupTimes(user_id: int, group_id: int, times: int):
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    cur.execute(
        "UPDATE cold_group_times SET times=? where user_id=? and group_id=?",
        (
            times,
            user_id,
            group_id,
        ),
    )
    conn.commit()
    conn.close()


# 获取冷群王次数
def GetColdGroupTimes(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT times FROM cold_group_times where user_id=? and group_id=?;",
            (user_id, group_id),
        )
    except sqlite3.OperationalError:
        logging.info("数据库表不存在,正在创建表cold_group_times")
        cur.execute(
            "CREATE TABLE cold_group_times ( user_id  INTEGER, group_id INTEGER, times INTEGER ); "
        )
        conn.commit()
        cur.execute(
            "SELECT times FROM cold_group_times where user_id=? and group_id=?;",
            (user_id, group_id),
        )
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO cold_group_times (user_id,group_id,times ) VALUES (?,?,?);",
            (user_id, group_id, 1),
        )
        conn.commit()
        conn.close()
        return 0
    else:
        conn.close()
        return data[0][0]


class ColdGroupKingChatApplication(MetaMessageApplication):
    def __init__(
        self,
    ):
        applicationInfo = ApplicationInfo("冷群王功能", "统计并回复冷群信息")
        super().__init__(
            applicationInfo, 100, True, ApplicationCostType.HIGH_TIME_HIGH_PERFORMANCE
        )

    async def process(self, message: MetaMessageInfo):
        for groupId in GetAllGroupId():
            if LoadGroupSetting("cold_king_switch", groupId, False):
                if time.time() - LoadGroupSetting(
                    "last_say_time", groupId, 0
                ) >= load_setting("cold_king_time", 300):
                    userId = LoadGroupSetting("cold_king_user_id", groupId, 0)
                    SetColdGroupTimes(
                        userId,
                        groupId,
                        GetColdGroupTimes(userId, groupId) + 1,
                    )
                    await chat(message.websocket, userId, groupId, 0, "")

    def judge(self, message: MetaMessageInfo) -> bool:
        """判断是否满足触发条件"""
        return message.metaEventType == MetaEventType.HEART_BEAT


class ColdGroupKingRefreshStatusApplication(GroupMessageApplication):
    def __init__(
        self,
    ):
        applicationInfo = ApplicationInfo("冷群王刷新", "刷新冷群王状态", False)
        super().__init__(applicationInfo, 100, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        if LoadGroupSetting("cold_king_switch", message.groupId, False):
            DumpGroupSetting("last_say_time", message.groupId, time.time())
            DumpGroupSetting("cold_king_user_id", message.groupId, message.senderId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否满足触发条件"""
        # 只有在群内开启了冷群王功能时才执行状态刷新
        return LoadGroupSetting("cold_king_switch", message.groupId, False)


