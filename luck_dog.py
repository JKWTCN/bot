import base64
from datetime import date
import random
import time
from Class.Ranking import Ranking
import bot_database
import matplotlib.pyplot as plt
import numpy as np
from tools import GetNowDay, load_setting
from rankings import update_value
import sqlite3
import json

choice_list = [200, 100, 50, 10, -10, -20, 444, 555, 666, 777]
choice_probability = [
    0.025,  # 200 0
    0.05,  # 100 1
    0.1,  # 50 2
    0.2,  # 10 3
    0.25,  # -10 4
    0.25,  # -20 5
    0.01,  # *2 6
    0.01,  # /2 7
    0.001,  # *10 8
    0.001,  # 0 9
]


# 获取抽奖限制
def GetGamblingTimesToday(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT today_num,today FROM gambling_today where user_id=? and group_id=?",
        (
            user_id,
            group_id,
        ),
    )
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO gambling_today (user_id,group_id,today_num,today)VALUES (?,?,?,?);",
            (user_id, group_id, 0, GetNowDay()),
        )
        conn.commit()
        return (0, GetNowDay())
    else:
        return (data[0][0], data[0][1])


# 改变今天的抽奖次数
def ChangeGameblingTimesToday(user_id: int, group_id: int, today_num: int, today: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE gambling_today SET today_num=?,today=? where user_id=? and group_id=?",
        (today_num, today, user_id, group_id),
    )
    conn.commit()


# 运势
def ys_simple(ys):
    if ys == 0:
        return "大吉喵，快买彩票喵。"
    elif ys < 20:
        return "吉"
    elif ys < 40:
        return "小吉"
    elif ys < 70:
        return "普通"
    elif ys < 99:
        return "凶"
    elif ys == 99:
        return "大凶，快去洗澡喵"


# 运势详情
async def luck_dog(websocket, use_id: int, sender_name: str, group_id: int):
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": "{},{}。".format(
                sender_name,
                ys_simple((date.today().day * use_id) % 100),
            ),
        },
    }
    await websocket.send(json.dumps(payload))


# 私聊抽奖
async def LuckChoiceMutPrivate(websocket, user_id: int, nums: int):
    group_id = 0
    setting = load_setting()
    payload = {
        "action": "send_msg",
        "params": {
            "user_id": user_id,
            "message": [],
        },
    }
    luck_list = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    start_point = bot_database.find_point(user_id)
    now_point = start_point
    x = []
    y = []
    x.append(0)
    y.append(start_point)
    for i in range(nums):
        if now_point >= 5:
            bot_database.add_gambling_times(user_id, 1)
            now_point = now_point - 5
            choice = random.choices(choice_list, choice_probability)
            match choice[0]:
                case 200:
                    luck_list[0] = luck_list[0] + 1
                    now_point = now_point + 200
                case 100:
                    luck_list[1] = luck_list[1] + 1
                    now_point = now_point + 100
                case 50:
                    luck_list[2] = luck_list[2] + 1
                    now_point = now_point + 50
                case 10:
                    luck_list[3] = luck_list[3] + 1
                    now_point = now_point + 10
                case -10:
                    luck_list[4] = luck_list[4] + 1
                    now_point = now_point - 10
                case -20:
                    luck_list[5] = luck_list[5] + 1
                    now_point = now_point - 20
                case 444:
                    luck_list[6] = luck_list[6] + 1
                    now_point = now_point * 2
                case 555:
                    luck_list[7] = luck_list[7] + 1
                    now_point = now_point / 2
                case 666:
                    luck_list[8] = luck_list[8] + 1
                    now_point = now_point * 10
                case 777:
                    luck_list[9] = luck_list[9] + 1
                    now_point = 0
            x.append(i + 1)
            y.append(now_point)
            bot_database.change_point(user_id, group_id, now_point)
            update_value(Ranking(user_id, group_id, now_point, time.time(), 1))
            if now_point <= 0:
                payload["params"]["message"].append(
                    {
                        "type": "text",
                        "data": {
                            "text": "结果统计如下：\n200积分奖:{}次\n100积分奖:{}次\n50积分奖:{}次\n10积分奖:{}次\n-10积分奖:{}次\n-20积分奖:{}次\n双倍积分奖:{}次\n折半积分奖:{}次\n十倍积分奖:{}次\n积分清零奖:{}次\n积分总额:{}->{}\n".format(
                                luck_list[0],
                                luck_list[1],
                                luck_list[2],
                                luck_list[3],
                                luck_list[4],
                                luck_list[5],
                                luck_list[6],
                                luck_list[7],
                                luck_list[8],
                                luck_list[9],
                                start_point,
                                now_point,
                            )
                        },
                    }
                )
                payload["params"]["message"].append(
                    {
                        "type": "text",
                        "data": {"text": "十赌九输喵,赌狗好似喵。"},
                    }
                )
                payload["params"]["message"].append(
                    {
                        "type": "image",
                        "data": {
                            "file": "base64://"
                            + open_chart_by_base64(user_id, group_id, x, y).decode(
                                "utf-8"
                            )
                        },
                    }
                )
                update_value(Ranking(user_id, group_id, now_point, time.time(), 1))
                await websocket.send(json.dumps(payload))
        payload["params"]["message"].append(
            {
                "type": "text",
                "data": {
                    "text": "抽奖统计如下：\n200积分奖:{}次\n100积分奖:{}次\n50积分奖:{}次\n10积分奖:{}次\n-10积分奖:{}次\n-20积分奖:{}次\n双倍积分奖:{}次\n折半积分奖:{}次\n十倍积分奖:{}次\n积分清零奖:{}次\n积分总额:{}->{}\n乐可:这次运气不错喵。".format(
                        luck_list[0],
                        luck_list[1],
                        luck_list[2],
                        luck_list[3],
                        luck_list[4],
                        luck_list[5],
                        luck_list[6],
                        luck_list[7],
                        luck_list[8],
                        luck_list[9],
                        start_point,
                        now_point,
                    )
                },
            }
        )
        payload["params"]["message"].append(
            {
                "type": "image",
                "data": {
                    "file": "base64://"
                    + open_chart_by_base64(user_id, group_id, x, y).decode("utf-8")
                },
            }
        )
    else:
        payload["params"]["message"].append(
            {
                "type": "text",
                "data": {
                    "text": "抽奖失败喵，至少要5积分喵。您当前积分为:{}。\n".format(
                        start_point
                    )
                },
            }
        )
    update_value(Ranking(user_id, group_id, now_point, time.time(), 1))
    await websocket.send(json.dumps(payload))


async def luck_choice_mut(
    websocket, user_id: int, sender_name: str, group_id: int, nums: int
):
    setting = load_setting()
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [],
        },
    }
    if group_id == setting["admin_group_main"]:
        payload["params"]["message"].append(
            {
                "type": "text",
                "data": {
                    "text": "{},主群的抽奖权限关闭了喵,去分群吧,分区群号:{}。".format(
                        sender_name, setting["sepcial_group"]
                    )
                },
            }
        )
        await websocket.send(json.dumps(payload))
    luck_list = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    start_point = bot_database.find_point(user_id)
    now_point = start_point
    today_num, today = GetGamblingTimesToday(user_id, group_id)
    x = []
    y = []
    if today != GetNowDay():
        today = GetNowDay()
        today_num = 0
    if today_num <= setting["gambling_limit"] and start_point >= 5:
        x.append(0)
        y.append(start_point)
        for i in range(nums):
            # now_point = bot_database.find_point(user_id)
            if now_point >= 5:
                bot_database.add_gambling_times(user_id, 1)
                now_point = now_point - 5
                choice = random.choices(choice_list, choice_probability)
                if group_id not in setting["sepcial_group"]:
                    today_num = today_num + 1
                match choice[0]:
                    case 200:
                        luck_list[0] = luck_list[0] + 1
                        now_point = now_point + 200
                    case 100:
                        luck_list[1] = luck_list[1] + 1
                        now_point = now_point + 100
                    case 50:
                        luck_list[2] = luck_list[2] + 1
                        now_point = now_point + 50
                    case 10:
                        luck_list[3] = luck_list[3] + 1
                        now_point = now_point + 10
                    case -10:
                        luck_list[4] = luck_list[4] + 1
                        now_point = now_point - 10
                    case -20:
                        luck_list[5] = luck_list[5] + 1
                        now_point = now_point - 20
                    case 444:
                        luck_list[6] = luck_list[6] + 1
                        now_point = now_point * 2
                    case 555:
                        luck_list[7] = luck_list[7] + 1
                        now_point = now_point / 2
                    case 666:
                        luck_list[8] = luck_list[8] + 1
                        now_point = now_point * 10
                    case 777:
                        luck_list[9] = luck_list[9] + 1
                        now_point = 0
                x.append(i + 1)
                y.append(now_point)
                bot_database.change_point(user_id, group_id, now_point)
                update_value(Ranking(user_id, group_id, now_point, time.time(), 1))
                if now_point <= 0 or today_num > setting["gambling_limit"]:
                    payload["params"]["message"].append(
                        {
                            "type": "text",
                            "data": {
                                "text": "{},抽奖统计如下：\n200积分奖:{}次\n100积分奖:{}次\n50积分奖:{}次\n10积分奖:{}次\n-10积分奖:{}次\n-20积分奖:{}次\n双倍积分奖:{}次\n折半积分奖:{}次\n十倍积分奖:{}次\n积分清零奖:{}次\n积分总额:{}->{}\n".format(
                                    sender_name,
                                    luck_list[0],
                                    luck_list[1],
                                    luck_list[2],
                                    luck_list[3],
                                    luck_list[4],
                                    luck_list[5],
                                    luck_list[6],
                                    luck_list[7],
                                    luck_list[8],
                                    luck_list[9],
                                    start_point,
                                    now_point,
                                )
                            },
                        }
                    )
                    if today_num > setting["gambling_limit"]:
                        payload["params"]["message"].append(
                            {
                                "type": "text",
                                "data": {
                                    "text": "今日已超过{}次,请明日再来喵。".format(
                                        setting["gambling_limit"]
                                    )
                                },
                            }
                        )
                    else:
                        payload["params"]["message"].append(
                            {
                                "type": "text",
                                "data": {"text": "十赌九输喵,赌狗好似喵。"},
                            }
                        )
                    payload["params"]["message"].append(
                        {
                            "type": "image",
                            "data": {
                                "file": "base64://"
                                + open_chart_by_base64(user_id, group_id, x, y).decode(
                                    "utf-8"
                                )
                            },
                        }
                    )
                    update_value(Ranking(user_id, group_id, now_point, time.time(), 1))
                    if group_id not in setting["sepcial_group"]:
                        ChangeGameblingTimesToday(user_id, group_id, today_num, today)
                    await websocket.send(json.dumps(payload))
        payload["params"]["message"].append(
            {
                "type": "text",
                "data": {
                    "text": "{},抽奖统计如下：\n200积分奖:{}次\n100积分奖:{}次\n50积分奖:{}次\n10积分奖:{}次\n-10积分奖:{}次\n-20积分奖:{}次\n双倍积分奖:{}次\n折半积分奖:{}次\n十倍积分奖:{}次\n积分清零奖:{}次\n积分总额:{}->{}\n乐可:这次运气不错喵。".format(
                        sender_name,
                        luck_list[0],
                        luck_list[1],
                        luck_list[2],
                        luck_list[3],
                        luck_list[4],
                        luck_list[5],
                        luck_list[6],
                        luck_list[7],
                        luck_list[8],
                        luck_list[9],
                        start_point,
                        now_point,
                    )
                },
            }
        )
        payload["params"]["message"].append(
            {
                "type": "image",
                "data": {
                    "file": "base64://"
                    + open_chart_by_base64(user_id, group_id, x, y).decode("utf-8")
                },
            }
        )
        if group_id not in setting["sepcial_group"]:
            ChangeGameblingTimesToday(user_id, group_id, today_num, today)
    elif today_num > setting["gambling_limit"]:
        payload["params"]["message"].append(
            {
                "type": "text",
                "data": {
                    "text": "{},抽奖失败喵,今天已经超过{}次了喵。".format(
                        sender_name, setting["gambling_limit"]
                    )
                },
            }
        )
    else:
        payload["params"]["message"].append(
            {
                "type": "text",
                "data": {
                    "text": "{},抽奖失败喵，至少要5积分喵。您当前积分为：{}。\n".format(
                        sender_name, start_point
                    )
                },
            }
        )
    update_value(Ranking(user_id, group_id, now_point, time.time(), 1))
    await websocket.send(json.dumps(payload))


# 5积分抽一次
# 200(0.025) 100(0.05) 50(0.10) 10(0.20) -10(0.5) 10*(0.001) 0*(0.001)
async def luck_choice(websocket, user_id: int, sender_name: str, group_id: int):
    now_point = bot_database.find_point(user_id)
    if now_point >= 5:
        bot_database.add_gambling_times(user_id, 1)
        now_point = now_point - 5
        choice = random.choices(choice_list, choice_probability)
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": "",
            },
        }
        if choice[0] == 666:
            changed_point = now_point * 10
            payload["params"]["message"] = "{},积分{}->{},10倍大奖喵。".format(
                sender_name, now_point, changed_point
            )
        elif choice[0] == 777:
            changed_point = 0
            payload["params"]["message"] = "{},赌狗好似喵,积分清零喵。".format(
                sender_name
            )
        elif choice[0] == 444:
            changed_point = now_point * 2
            payload["params"]["message"] = "{},积分{}->{},二倍奖喵。".format(
                sender_name, now_point, changed_point
            )
        elif choice[0] == 555:
            changed_point = now_point / 2
            payload["params"]["message"] = "{},积分{}->{},折半奖喵。".format(
                sender_name, now_point, changed_point
            )
        else:
            changed_point = now_point + choice[0]
            if changed_point >= 0:
                payload["params"]["message"] = "{},抽奖成功喵,积分{}->{}。".format(
                    sender_name, now_point, changed_point
                )
            else:
                payload["params"]["message"] = (
                    "{},积分{}->{},十赌九输喵,负债累累喵。".format(
                        sender_name, now_point, changed_point
                    )
                )
        update_value(Ranking(user_id, group_id, now_point, time.time(), 1))
        bot_database.change_point(user_id, group_id, changed_point)
    else:
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": "{},抽奖失败喵，至少要5积分喵。您当前积分为：{}。".format(
                    sender_name, now_point
                ),
            },
        }
    # print(payload)
    await websocket.send(json.dumps(payload))


def open_chart_by_base64(user_id: int, group_id: int, x, y):
    plt.plot(x, y)
    plt.savefig("figs/point_fig.jpg")
    plt.close()
    with open("figs/point_fig.jpg", "rb") as image_file:
        image_data = image_file.read()
    return base64.b64encode(image_data)


# create_line_chart(1,2,[1,2,3],[1,2,3])
