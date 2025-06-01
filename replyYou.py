import base64
import sqlite3
import time
from tools import GetNowDay
import matplotlib.pyplot as plt
from plottable import Table
import pandas as pd
import json


"""
CREATE TABLE reply_you (
    user_id           INTEGER,
    group_id          INTEGER,
    all_reply_times   INTEGER,
    today             INTEGER,
    today_reply_times INTEGER
);

"""


def ShowTableByBase64(data):
    """根据数据生成表格base64"""
    plt.rcParams["font.sans-serif"] = ["AR PL UKai CN"]
    # plt.rcParams["font.sans-serif"] = ["Unifont"]  # 设置字体
    # plt.rcParams["font.sans-serif"] = ["SimHei"]  # 设置字体
    plt.rcParams["axes.unicode_minus"] = False  # 正常显示负号
    table = pd.DataFrame(data)
    fig, ax = plt.subplots()
    table = table.set_index("排名")
    Table(table)
    plt.title("水群排名")
    plt.savefig("figs/reply_you_table.png", dpi=460)
    plt.close()
    with open("figs/reply_you_table.png", "rb") as image_file:
        image_data = image_file.read()
    return base64.b64encode(image_data)


async def getLifeReplyYouRecord(websocket, group_id: int):
    """获取生涯被理会数排名"""
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id,all_reply_times FROM reply_you WHERE group_id=? ORDER BY all_reply_times DESC ;",
        (group_id,),
    )
    data = cur.fetchall()
    num: int = 0
    if len(data) == 0:
        await websocket.send(json.dumps(payload))
    elif len(data) <= 20:
        num = len(data)
    else:
        num = 20
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [],
        },
    }
    table_list = {"排名": [], "昵称": [], "QQ": [], "生涯次数": []}
    for i in range(num):
        from Class.Group_member import get_user_name

        name = get_user_name(data[i][0], group_id)
        table_list["排名"].append(i + 1)
        table_list["QQ"].append(data[i][0])
        table_list["昵称"].append(name)
        table_list["生涯次数"].append(data[i][1])
    payload["params"]["message"].append(
        {
            "type": "image",
            "data": {
                "file": "base64://" + ShowTableByBase64(table_list).decode("utf-8")
            },
        }
    )
    await websocket.send(json.dumps(payload))


async def getTodayReplyYouRecord(websocket, group_id: int):
    """统计今日被理会排名"""
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id,today_reply_times FROM reply_you WHERE group_id=? and today=? ORDER BY today_num DESC ;",
        (
            group_id,
            GetNowDay(),
        ),
    )
    data = cur.fetchall()
    num: int = 0
    if len(data) == 0:
        await websocket.send(json.dumps(payload))
    elif len(data) <= 20:
        num = len(data)
    else:
        num = 20
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [],
        },
    }
    table_list = {"排名": [], "昵称": [], "QQ": [], "今日次数": []}
    for i in range(num):
        from Class.Group_member import get_user_name

        name = get_user_name(data[i][0], group_id)
        table_list["排名"].append(i + 1)
        table_list["QQ"].append(data[i][0])
        table_list["昵称"].append(name)
        table_list["今日次数"].append(data[i][1])
    payload["params"]["message"].append(
        {
            "type": "image",
            "data": {
                "file": "base64://" + ShowTableByBase64(table_list).decode("utf-8")
            },
        }
    )
    await websocket.send(json.dumps(payload))


def getReplyYouTimes(user_id: int, group_id: int):
    """获取被理会数"""
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT all_reply_times,today_reply_times,today FROM reply_you where user_id=? and group_id=?;",
        (
            user_id,
            group_id,
        ),
    )
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO reply_you (user_id,group_id,all_reply_times,today_reply_times,today)\
                VALUES (?,?,?,?,?);",
            (user_id, group_id, 0, 0, GetNowDay()),
        )
        conn.commit()
        cur.execute(
            "SELECT all_reply_times,today_reply_times,today FROM reply_you where user_id=? and group_id=?;",
            (
                user_id,
                group_id,
            ),
        )
        data = cur.fetchall()
        conn.close()
    conn.close()
    all_num = data[0][0]
    today_num = data[0][1]
    today = data[0][2]
    return (today_num, all_num, today)


def incReplyYouTimes(user_id: int, group_id: int):
    """自增被理会数目"""

    today_num, all_num, today = getReplyYouTimes(user_id, group_id)
    all_num += 1
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    if today != GetNowDay():
        today_num = 1
        today = GetNowDay()
    else:
        today_num = today_num + 1
    cur.execute(
        "UPDATE reply_you SET all_reply_times = ?,today_reply_times = ?,today = ?\
            WHERE user_id = ? AND group_id = ?;",
        (all_num, today_num, today, user_id, group_id),
    )
    conn.commit()
    conn.close()
    return (all_num, today_num)


"""
CREATE TABLE who_reply_you (
    user_id  INTEGER,
    reply_id INTEGER,
    group_id INTEGER,
    time     INTEGER
);
"""


def addWhoReplyYou(user_id: int, reply_id: int, group_id: int):
    """添加reply记录"""
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO who_reply_you (user_id,reply_id,group_id,time)\
                VALUES (?,?,?,?);",
        (user_id, reply_id, group_id, time.time()),
    )
    conn.commit()
    conn.close()
