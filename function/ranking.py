import base64
from enum import Enum
import sqlite3
import time

from matplotlib import pyplot as plt
import pandas as pd
from plottable import Table

from function.datebase_user import get_user_info, is_in_group


class Ranking:
    user_id: int
    group_id: int
    max_value: int
    time: int
    type: int

    def __init__(
        self, user_id: int, group_id: int, max_value: int, time: int, type: int
    ):
        self.user_id = user_id
        self.group_id = group_id
        self.max_value = max_value
        self.time = time
        self.type = type


class User_point:
    user_id: int
    point: int
    time: int

    def __init__(self, user_id: int, point: int, time: int):
        self.user_id = user_id
        self.point = point
        self.time = time


import json


class Type(Enum):
    point_max = 1


def find_value(type: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM rankings where type=? and group_id=?", (type, group_id))
    data = cur.fetchall()
    if len(data) == 0:
        return (False, Ranking(0, 0, 0, 0, 0))
    else:
        ranking = Ranking(data[0][0], data[0][1], data[0][2], data[0][3], data[0][4])
        return (True, ranking)


def update_value(new_ranking: Ranking):
    (is_exist, ranking) = find_value(new_ranking.type, new_ranking.group_id)
    if (
        is_exist
        and new_ranking.type is Type.point_max.value
        and new_ranking.max_value > ranking.max_value
    ):
        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()
        cur.execute(
            "UPDATE rankings SET max_value=?,time=? ,user_id=? where  group_id=? and type=?",
            (
                new_ranking.max_value,
                time.time(),
                new_ranking.user_id,
                new_ranking.group_id,
                new_ranking.type,
            ),
        )
        conn.commit()
        conn.close()
    elif not is_exist:
        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO rankings VALUES(?,?,?,?,?)",
            (
                new_ranking.user_id,
                new_ranking.group_id,
                new_ranking.max_value,
                time.time(),
                new_ranking.type,
            ),
        )
        conn.commit()
        conn.close()


def find_points_ranking():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM user_point ORDER BY point DESC")
    data = cur.fetchall()
    # print(data)
    if len(data) == 0:
        return (False, [])
    else:
        points_list = []
        for user in data:
            # print(user)
            points_list.append(User_point(user[0], user[1], user[2]))
        return (True, points_list)


# 群友积分统计表格
def ShowRankingByBase64(data):
    plt.rcParams["font.sans-serif"] = ["AR PL UKai CN"]
    # plt.rcParams["font.sans-serif"] = ["Unifont"]  # 设置字体
    # plt.rcParams["font.sans-serif"] = ["SimHei"]  # 设置字体
    plt.rcParams["axes.unicode_minus"] = False  # 正常显示负号
    table = pd.DataFrame(data)
    fig, ax = plt.subplots()
    table = table.set_index("积分排名")
    Table(table)
    plt.title("积分排名")
    plt.savefig("figs/point_table.png", dpi=460)
    plt.close()
    with open("figs/point_table.png", "rb") as image_file:
        image_data = image_file.read()
    return base64.b64encode(image_data)


# 积分排名
async def ranking_point_payload(websocket, group_id: int):
    data_list = {"积分排名": [], "昵称": [], "QQ": [], "值": []}
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [],
        },
    }
    (is_exist, points_list) = find_points_ranking()
    true_points_list = []
    for points_info in points_list:
        if is_in_group(points_info.user_id, group_id):
            true_points_list.append(points_info)
    if is_exist:
        i = 0
        j = 0
        if len(true_points_list) < 10:
            num = len(true_points_list)
        else:
            num = 10
        while j < num:
            res, user_info = get_user_info(points_list[i].user_id, group_id)
            if res:
                name = ""
                # print(user_info.card)
                if user_info.card != "":
                    name = user_info.card
                else:
                    name = user_info.nickname
                data_list["积分排名"].append(j + 1)
                data_list["QQ"].append(points_list[i].user_id)
                data_list["昵称"].append(name)
                data_list["值"].append(points_list[i].point)
                j += 1
            i += 1
    payload["params"]["message"].append(
        {
            "type": "image",
            "data": {
                "file": "base64://" + ShowRankingByBase64(data_list).decode("utf-8")
            },
        }
    )
    (is_exist, ranking) = find_value(1, group_id)
    if is_exist:
        res, user_info = get_user_info(ranking.user_id, group_id)
        if res:
            if user_info.card != "":
                name = user_info.card
            else:
                name = user_info.nickname
        else:
            name = ranking.user_id

        payload["params"]["message"].append(
            {
                "type": "text",
                "data": {
                    "text": "本群积分历史最高为{}分,由{}于{}创造喵。".format(
                        ranking.max_value,
                        name,
                        time.strftime(
                            "%Y年%m月%d日%H:%M:%S", time.localtime(ranking.time)
                        ),
                    )
                },
            },
        )
    # print(payload)
    await websocket.send(json.dumps(payload))


# print(find_value(1)[1].max_value)
# ranking_point_payload()
