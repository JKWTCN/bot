import base64
import sqlite3
from tools import GetNowDay
import logging
import matplotlib.pyplot as plt
from plottable import Table
import pandas as pd


# 群友水群次数表格
def ShowTableByBase64(data):
    # plt.rcParams["font.sans-serif"] = ["Unifont"]  # 设置字体
    plt.rcParams["font.sans-serif"] = ["SimHei"]  # 设置字体
    plt.rcParams["axes.unicode_minus"] = False  # 正常显示负号
    table = pd.DataFrame(data)
    fig, ax = plt.subplots(figsize=(8, 8))
    table = table.set_index("排名")
    Table(table)
    plt.title("水群排名")
    plt.savefig("figs/chat_table.jpg")
    plt.close()
    with open("figs/chat_table.jpg", "rb") as image_file:
        image_data = image_file.read()
    return base64.b64encode(image_data)


# 统计生涯水群次数
def GetLifeChatRecord(group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id,all_num FROM ChatRecord WHERE group_id=? ORDER BY all_num DESC ;",
        (group_id,),
    )
    data = cur.fetchall()
    num: int = 0
    if len(data) == 0:
        return payload
    elif len(data) <= 30:
        num = len(data)
    else:
        num = 30
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [],
        },
    }
    table_list = {"排名": [], "昵称": [], "生涯次数": []}
    for i in range(num):
        from Class.Group_member import get_user_name

        name = get_user_name(data[i][0], group_id)
        table_list["排名"].append(i + 1)
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
    return payload


# 统计今日水群次数
def GetNowChatRecord(group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id,today_num FROM ChatRecord WHERE group_id=? and today=? ORDER BY today_num DESC ;",
        (group_id,GetNowDay(),),
    )
    data = cur.fetchall()
    num: int = 0
    if len(data) == 0:
        return payload
    elif len(data) <= 30:
        num = len(data)
    else:
        num = 30
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [],
        },
    }
    table_list = {"排名": [], "昵称": [], "次数": []}
    for i in range(num):
        from Class.Group_member import get_user_name

        name = get_user_name(data[i][0], group_id)
        table_list["排名"].append(i + 1)
        table_list["昵称"].append(name)
        table_list["次数"].append(data[i][1])
    payload["params"]["message"].append(
        {
            "type": "image",
            "data": {
                "file": "base64://" + ShowTableByBase64(table_list).decode("utf-8")
            },
        }
    )
    return payload


# 统计水群次数
def AddChatRecord(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT all_num,today_num,today FROM ChatRecord where user_id=? and group_id=?;",
        (
            user_id,
            group_id,
        ),
    )
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO ChatRecord (user_id,group_id,all_num,today_num,today)\
                VALUES (?,?,?,?,?);",
            (user_id, group_id, 0, 0, GetNowDay()),
        )
        conn.commit()
        cur.execute(
            "SELECT all_num,today_num,today FROM ChatRecord where user_id=? and group_id=?;",
            (
                user_id,
                group_id,
            ),
        )
        data = cur.fetchall()
    all_num = data[0][0]
    today_num = data[0][1]
    today = data[0][2]
    all_num = all_num + 1
    if today != GetNowDay():
        today_num = 1
        today = GetNowDay()
    else:
        today_num = today_num + 1
    cur.execute(
        "UPDATE ChatRecord SET all_num = ?,today_num = ?,today = ?\
            WHERE user_id = ? AND group_id = ?;",
        (all_num, today_num, today, user_id, group_id),
    )
    conn.commit()
    return (all_num, today_num)
