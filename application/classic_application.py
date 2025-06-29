from datetime import datetime
import json
import random
import sqlite3
import time
from data.message.group_message_info import GroupMessageInfo
from data.application.application_info import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from data.enumerates import ApplicationCostType

from function.say import SayGroup, ReplySay
from function.datebase_user import IsAdmin, get_user_name
from function.GroupConfig import manage_config, GroupConfigError
from function.ranking import update_value, Ranking


# 签到应用
def check_in(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM user_point where user_id=?", (user_id,))
    data = cur.fetchall()
    now_point = -1
    now_time = 0
    # print(len(data))
    if len(data) == 0:
        update_value(Ranking(user_id, group_id, 0, int(time.time()), 1))
        cur.execute("INSERT INTO user_point VALUES(?,?,?)", (user_id, 0, 0))
        conn.commit()
        conn.close()
        now_point = 0
        now_time = datetime.fromtimestamp(0)
    else:
        now_point = data[0][1]
        now_time = datetime.fromtimestamp(data[0][2])
    if now_time.day - datetime.now().day != 0:
        now_point = now_point + random.randint(1, 50)
        cur.execute(
            "UPDATE user_point SET point=?,time=? WHERE user_id=?",
            (now_point, datetime.timestamp(datetime.now()), user_id),
        )
        conn.commit()
        conn.close()
        update_value(Ranking(user_id, group_id, now_point, int(time.time()), 1))
        return (1, now_point)
    else:
        conn.close()
        return (0, now_point)


async def daily_check_in(websocket, user_id: int, sender_name: str, group_id: int):
    result = check_in(user_id, group_id)
    if result[0] == 1:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": "{},签到成功,您当前的积分为:{}。".format(
                    sender_name, result[1]
                ),
            },
        }
    else:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": "{},你今天已经签过到了,明天再来吧!您当前的积分为:{}。".format(
                    sender_name, result[1]
                ),
            },
        }
    await websocket.send(json.dumps(payload))


class CheckInApplication(GroupMessageApplication):

    def __init__(self):
        applicationInfo = ApplicationInfo("签到应用", "签到功能")
        super().__init__(applicationInfo, 65, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        """处理消息"""
        await daily_check_in(
            message.websocket,
            message.senderId,
            get_user_name(message.senderId, message.groupId),
            message.groupId,
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        return "签到" in message.painTextMessage

