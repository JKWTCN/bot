import sqlite3
import time
from Class.Group_member import IsAdmin
import bot_database
import tools
import json


# 获取群聊名称
def GetGroupName(group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT group_name FROM group_info where group_id=?;",
        (group_id,),
    )
    data = cur.fetchall()
    if len(data) == 0:
        return group_id
    else:
        return data[0][0]


# 更新群列表
def update_group_info(
    group_id: int, group_name: str, member_count: int, max_member_count: int
):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM group_info where group_id=?;",
        (group_id,),
    )
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO group_info (group_id,group_name,member_count,max_member_count)VALUES (?,?,?,?);",
            (group_id, group_name, member_count, max_member_count),
        )
        conn.commit()
    else:
        cur.execute(
            "UPDATE group_info SET group_name = ?,member_count=?,max_member_count=? WHERE group_id = ?;",
            (
                group_name,
                member_count,
                max_member_count,
                group_id,
            ),
        )
        conn.commit()


# 发送获取群名单
async def get_group_list(websocket):
    payload = {
        "action": "get_group_list",
        "echo": "get_group_list",
    }
    await websocket.send(json.dumps(payload))


# 设置群聊精华信息
async def SetEssenceMsg(websocket, message_id: int):
    payload = {
        "action": "set_essence_msg",
        "params": {
            "message_id": message_id,
        },
    }
    await websocket.send(json.dumps(payload))


# 移除群聊精华信息
async def DeleteEssenceMsg(websocket, message_id: int):
    payload = {
        "action": "delete_essence_msg",
        "params": {
            "message_id": message_id,
        },
    }
    await websocket.send(json.dumps(payload))


# 全体禁言
async def SetGroupWholeBan(websocket, group_id: int):
    payload = {
        "action": "set_group_whole_ban",
        "params": {"group_id": group_id, "enable": True},
    }
    await websocket.send(json.dumps(payload))


# 解除全体禁言
async def SetGroupWholeNoBan(websocket, group_id: int):
    payload = {
        "action": "set_group_whole_ban",
        "params": {"group_id": group_id, "enable": False},
    }
    await websocket.send(json.dumps(payload))


# 踢人
async def kick_member(websocket, user_id: int, group_id: int):
    payload = {
        "action": "set_group_kick",
        "params": {
            "user_id": user_id,
            "group_id": group_id,
        },
    }
    # print(payload)
    await websocket.send(json.dumps(payload))


# 发群低保
async def poor_point(websocket, user_id: int, group_id: int, sender_name: str):
    now_point = bot_database.find_point(user_id)
    if now_point <= 0:
        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM poor where user_id=? and group_id=?;",
            (
                user_id,
                group_id,
            ),
        )
        data = cur.fetchall()
        if len(data) == 0:
            cur.execute(
                "INSERT INTO poor (user_id,group_id,times,time)VALUES (?,?,?,?);",
                (user_id, group_id, 0, time.time()),
            )
            conn.commit()
            cur.execute(
                "SELECT * FROM poor where user_id=? and group_id=?;",
                (
                    user_id,
                    group_id,
                ),
            )
            data = cur.fetchall()
        if data[0][2] < 3:
            cur.execute(
                "UPDATE poor SET times = ? WHERE user_id = ? AND group_id = ?;",
                (data[0][2] + 1, user_id, group_id),
            )
            conn.commit()
            bot_database.change_point(user_id, group_id, 5)
            payload = {
                "action": "send_msg",
                "params": {
                    "group_id": group_id,
                    "message": "{},领取群低保成功喵，目前你的积分为:5。({}/3)".format(
                        sender_name, data[0][2] + 1
                    ),
                },
            }
        elif data[0][2] >= 3 and tools.is_today(time.time(), data[0][3]):
            payload = {
                "action": "send_msg",
                "params": {
                    "group_id": group_id,
                    "message": "{},领取群低保失败喵,领取群低保次数达到今日上限了喵,请明天再来喵。".format(
                        sender_name
                    ),
                },
            }
        elif data[0][2] >= 3 and not tools.is_today(time.time(), data[0][3]):
            cur.execute(
                "UPDATE poor SET times = ?,time=? WHERE user_id = ? AND group_id = ?;",
                (1, time.time(), user_id, group_id),
            )
            conn.commit()
            payload = {
                "action": "send_msg",
                "params": {
                    "group_id": group_id,
                    "message": "{},领取群低保成功喵，目前你的积分为:5。(1/3)".format(
                        sender_name
                    ),
                },
            }

    else:
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": "{},你不符合群低保领取条件。".format(sender_name),
            },
        }
    await websocket.send(json.dumps(payload))
