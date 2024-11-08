import sqlite3
import time
import bot_database
import tools


def get_group_member_list(group_id: int):
    payload = {
        "action": "get_group_member_list",
        "params": {
            "group_id": group_id,
        },
        "echo": "update_group_member_list",
    }
    return payload


def kick_member(user_id: int, group_id: int):
    payload = {
        "action": "set_group_kick",
        "params": {
            "user_id": user_id,
            "group_id": group_id,
        },
    }
    # print(payload)
    return payload


def poor_point(user_id: int, group_id: int, sender_name: str):
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
    return payload
