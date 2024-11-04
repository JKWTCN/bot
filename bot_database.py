import sqlite3
from datetime import datetime
import random
import json
import time
from rankings import update_value
from Class.Ranking import Ranking


# 统计群友抽奖次数
def find_gambling_times(user_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT times FROM gambling where user_id=?", (user_id,))
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO gambling VALUES(?,?)",
            (
                user_id,
                0,
            ),
        )
        conn.commit()
        conn.close()
        return 0
    else:
        # print(data)
        return data[0][0]


def in_unwelcome(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM unwelcome where user_id=? and group_id=?", (user_id, group_id)
    )
    data = cur.fetchall()
    # print(data[0][1])
    conn.close()
    if len(data) != 0:
        return (True, data[0][1])
    return (False, 0)


def add_gambling_times(user_id: int, add_times: int):
    now_times = find_gambling_times(user_id)
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE gambling SET times=? WHERE user_id=?",
        (
            now_times + add_times,
            user_id,
        ),
    )
    conn.commit()
    conn.close()


def find_point(user_id):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM user_point where user_id=?", (user_id,))
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute("INSERT INTO user_point VALUES(?,?,?)", (user_id, 50, 0))
        conn.commit()
        conn.close()
        return 0
    else:
        # print(data[0][1])
        conn.close()
        return data[0][1]
        # return cur.fetchall()


def get_last_time_get_group_member_list():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT record_time FROM record where record_name=?",
        ("last_time_get_group_member_list",),
    )
    data = cur.fetchall()
    conn.close()
    return data[0][0]


def updata_last_time_get_group_member_list():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE record SET record_time=? WHERE record_name=?",
        (time.time(), "last_time_get_group_member_list"),
    )
    conn.commit()
    conn.close()


def add_unwelcome(user_id: int, time: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO unwelcome VALUES(?,?,?)", (user_id, time, group_id))
    conn.commit()
    conn.close()


def write_message(message: json):
    sender = message["sender"]
    sender_name = sender["card"]
    if len(sender["card"]) == 0:
        sender_name = sender["nickname"]
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO group_message VALUES(?,?,?,?,?,?,?,?)",
        (
            message["time"],
            message["user_id"],
            sender_name,
            message["raw_message"],
            message["group_id"],
            message["self_id"],
            message["sub_type"],
            message["message_id"],
        ),
    )
    conn.commit()
    conn.close()


def recharge(user_id: int, group_id: int, point: int):
    now_point = find_point(user_id)
    change_point(user_id, group_id, now_point + point)
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": "充值成功,积分{}->{}。".format(now_point, now_point + point),
        },
    }
    return payload


def recharge_privte(user_id: int, group_id: int, point: int):
    now_point = find_point(user_id)
    change_point(user_id, group_id, now_point + point)
    payload = {
        "action": "send_msg",
        "params": {
            "user_id": user_id,
            "message": "充值成功,积分{}->{}。".format(now_point, now_point + point),
        },
    }
    return payload


def changed_russian_pve(user_id: int, shots: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("UPDATE russian_pve SET shots=? WHERE user_id=?", (shots, user_id))
    conn.commit()
    conn.close()


def delete_russian_pve(user_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("delete FROM russian_pve where user_id=?", (user_id,))
    conn.commit()
    conn.close()


def check_russian_pve(user_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM russian_pve where user_id=?", (user_id,))
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute("INSERT INTO russian_pve VALUES(?,?)", (user_id, 6))
        conn.commit()
        conn.close()
        return -1
    else:
        return data[0][1]


def change_point(user_id: int, group_id: int, point: int):
    update_value(Ranking(user_id, group_id, point, time.time(), 1))
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE user_point SET point=? WHERE user_id=?",
        (point, user_id),
    )
    conn.commit()
    conn.close()


def check_in(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM user_point where user_id=?", (user_id,))
    data = cur.fetchall()
    now_point = -1
    now_time = 0
    # print(len(data))
    if len(data) == 0:
        update_value(Ranking(user_id, group_id, 0, time.time(), 1))
        cur.execute("INSERT INTO user_point VALUES(?,?,?)", (user_id, 0, 0))
        conn.commit()
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
        update_value(Ranking(user_id, group_id, now_point, time.time(), 1))
        conn.commit()
        conn.close()
        return (1, now_point)
    else:
        conn.close()
        return (0, now_point)


def get_statistics(user_id: int, group_id: int):
    now_point = find_point(user_id)
    gambling_times = find_gambling_times(user_id)
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {
                    "type": "text",
                    "data": {
                        "text": ",您目前的积分为：{}，您的总抽奖次数为:{}".format(
                            now_point, gambling_times
                        )
                    },
                },
            ],
        },
    }
    return payload


def daily_check_in(user_id: int, sender_name: str, group_id: int):
    result = check_in(user_id, group_id)
    if result[0] == 1:
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": "{},签到成功,您当前的积分为:{}。".format(
                    sender_name, result[1]
                ),
            },
        }
    else:
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": "{},你今天已经签过到了,明天再来吧!您当前的积分为:{}。".format(
                    sender_name, result[1]
                ),
            },
        }
    return payload
