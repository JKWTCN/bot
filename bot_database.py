import logging
import sqlite3
from datetime import datetime
import random
import json
import time
from chat import GetColdGroupTimes
from group_operate import GetGroupName
from kohlrabi import GetMyKohlrabi, GetRecordKohlrabi
from level import get_level
from rankings import update_value
from Class.Ranking import Ranking
from chat_record import GetChatRecord


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


# 判断是否在不欢迎名单
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


# 增加数据库记录的总抽奖次数
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


# 查找积分
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
        return round(data[0][1], 3)
        # return cur.fetchall()


# 获取上次获取群成员列表的时间
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


# 更新上次获取群成员列表的时间
def updata_last_time_get_group_member_list():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE record SET record_time=? WHERE record_name=?",
        (time.time(), "last_time_get_group_member_list"),
    )
    conn.commit()
    conn.close()


# 添加不欢迎名单
def add_unwelcome(user_id: int, time: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO unwelcome VALUES(?,?,?)", (user_id, time, group_id))
    conn.commit()
    conn.close()


# 信息写入数据库
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


# 充值积分
async def recharge(websocket, user_id: int, group_id: int, point: int):
    now_point = find_point(user_id)
    change_point(user_id, group_id, now_point + point)
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": "充值成功,积分{}->{}。".format(now_point, now_point + point),
        },
    }
    await websocket.send(json.dumps(payload))


# 私聊充值积分
async def recharge_privte(websocket, user_id: int, group_id: int, point: int):
    now_point = find_point(user_id)
    change_point(user_id, group_id, now_point + point)
    payload = {
        "action": "send_msg_async",
        "params": {
            "user_id": user_id,
            "message": "充值成功,积分{}->{}。".format(now_point, now_point + point),
        },
    }
    await websocket.send(json.dumps(payload))


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


from Class.Group_member import get_user_name


def change_point(user_id: int, group_id: int, point: int):
    if point >= 9223372036854775807:
        logging.info(
            f"{get_user_name(user_id, group_id)}({user_id}),在群{GetGroupName(group_id)}({group_id})爆分了!!!"
        )
        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()
        cur.execute(
            "UPDATE user_point SET point=? WHERE user_id=?",
            (0, user_id),
        )
        conn.commit()
        conn.close()
        return False
    point = round(point, 3)
    try:
        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()
        cur.execute(
            "UPDATE user_point SET point=? WHERE user_id=?",
            (point, user_id),
        )
    except OverflowError:
        logging.info(
            f"{get_user_name(user_id, group_id)}({user_id}),在群{GetGroupName(group_id)}({group_id})爆分了!!!"
        )
        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()
        cur.execute(
            "UPDATE user_point SET point=? WHERE user_id=?",
            (0, user_id),
        )
        conn.commit()
        conn.close()
        return False
    update_value(Ranking(user_id, group_id, point, time.time(), 1))
    conn.commit()
    conn.close()
    return True


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
        update_value(Ranking(user_id, group_id, now_point, time.time(), 1))
        return (1, now_point)
    else:
        conn.close()
        return (0, now_point)


# 群友水群次数表格
def ShowStatisticsTableByBase64(data, name: str):
    import matplotlib.pyplot as plt
    from plottable import Table
    import pandas as pd
    import base64

    plt.rcParams["font.sans-serif"] = ["Unifont"]  # 设置字体
    # plt.rcParams["font.sans-serif"] = ["SimHei"]  # 设置字体
    plt.rcParams["axes.unicode_minus"] = False  # 正常显示负号
    table = pd.DataFrame(data)
    fig, ax = plt.subplots()
    table = table.set_index("项目")
    Table(table)
    plt.title(f"{name}的生涯统计")
    plt.savefig("figs/statistics_table.png", dpi=460)
    plt.close()
    with open("figs/statistics_table.png", "rb") as image_file:
        image_data = image_file.read()
    return base64.b64encode(image_data)


async def get_statistics(websocket, user_id: int, group_id: int):
    from Class.Group_member import get_user_name

    now_point = find_point(user_id)
    gambling_times = find_gambling_times(user_id)
    now_num = GetMyKohlrabi(user_id, group_id)
    from chat_rewards import SendRewards

    all_num, today_num = SendRewards(user_id, group_id)
    (all_buy, all_buy_cost, all_sell, all_sell_price) = GetRecordKohlrabi(
        user_id, group_id
    )
    _check_num = round(all_sell_price - all_buy_cost, 3)
    _cold_king_times = GetColdGroupTimes(user_id, group_id)
    _today_chat_times, _all_chat_times = GetChatRecord(user_id, group_id)
    _now_level = get_level(user_id, group_id)
    data = {
        "项目": [
            "目前积分",
            "总抽奖次数",
            "今日水群积分次数",
            "生涯水群积分次数",
            "大头菜库存",
            "生涯买入个数",
            "生涯买入花费",
            "生涯卖出个数",
            "生涯卖出赚入",
            "大头菜贸易利润",
            "今日水群次数",
            "生涯水群次数",
            "冷群王次数",
            "积分等级",
        ],
        "值": [
            now_point,
            gambling_times,
            today_num,
            all_num,
            now_num,
            all_buy,
            all_buy_cost,
            all_sell,
            all_sell_price,
            _check_num,
            _today_chat_times,
            _all_chat_times,
            _cold_king_times,
            _now_level,
        ],
    }
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [],
        },
    }
    payload["params"]["message"].append(
        {
            "type": "image",
            "data": {
                "file": "base64://"
                + ShowStatisticsTableByBase64(
                    data, get_user_name(user_id, group_id)
                ).decode("utf-8")
            },
        }
    )
    await websocket.send(json.dumps(payload))


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
