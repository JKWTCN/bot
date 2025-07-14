import json
import random
import sqlite3
import time
import matplotlib.pyplot as plt
import base64

from data.application.group_message_application import GroupMessageApplication
from data.enumerates import ApplicationCostType
from function.datebase_other import change_point, find_point
from function.datebase_user import get_user_name
from data.message.group_message_info import GroupMessageInfo
from function.ranking import update_value, Ranking
from function.say import SayAndAt
from tools.tools import load_setting, HasAllKeyWords, HasKeyWords, is_today, GetNowDay
from data.application.application_info import ApplicationInfo
from application.classic_application import (
    GetMyKohlrabi,
    ChangeMyKohlrabi,
    get_level,
    set_level,
)


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


# 改变今天的抽奖次数
def ChangeGameblingTimesToday(user_id: int, group_id: int, today_num: int, today: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE gambling_today SET today_num=?,today=? where user_id=? and group_id=?",
        (today_num, today, user_id, group_id),
    )
    conn.commit()
    conn.close()


# 表格转base64
def open_chart_by_base64(x, y):
    plt.plot(x, y)
    plt.savefig("figs/point_fig.png", dpi=460)
    plt.close()
    with open("figs/point_fig.png", "rb") as image_file:
        image_data = image_file.read()
    return base64.b64encode(image_data)


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
        conn.close()
        return (0, GetNowDay())
    else:
        conn.close()
        return (data[0][0], data[0][1])


# 超过100w用的抽奖选项
async def luck_choice_mut_super_rich(
    websocket, user_id: int, sender_name: str, group_id: int, nums: int
):
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [],
        },
        "echo": "delete_message_list",
    }
    # today_num, today = GetGamblingTimesToday(user_id, group_id)
    x = []
    y = []
    luck_list = [0, 0, 0, 0, 0, 0, 0, 0, 0]
    start_point = find_point(user_id)
    rich_choice_list = ["*10", "*8", "*4", "*2", "*1", "/2", "/4", "/8", "0"]
    rich_choice_probability = [0.0625, 0.125, 0.25, 0.5, 1, 0.5, 0.25, 0.125, 0.0625]
    now_point = start_point
    if start_point >= 5:
        x.append(0)
        y.append(start_point)
        for i in range(nums):
            if now_point >= 5:
                add_gambling_times(user_id, 1)
                now_point = now_point - 5
                choice = random.choices(rich_choice_list, rich_choice_probability)
                match choice[0]:
                    case "*10":
                        now_point = now_point * 10
                        luck_list[0] = luck_list[0] + 1
                    case "*8":
                        now_point = now_point * 8
                        luck_list[1] = luck_list[1] + 1
                    case "*4":
                        now_point = now_point * 4
                        luck_list[2] = luck_list[2] + 1
                    case "*2":
                        now_point = now_point * 2
                        luck_list[3] = luck_list[3] + 1
                    case "*1":
                        now_point = now_point * 1
                        luck_list[4] = luck_list[4] + 1
                    case "/2":
                        now_point = now_point / 2
                        luck_list[5] = luck_list[5] + 1
                    case "/4":
                        now_point = now_point / 4
                        luck_list[6] = luck_list[6] + 1
                    case "/8":
                        now_point = now_point / 8
                        luck_list[7] = luck_list[7] + 1
                    case "0":
                        now_point = 0
                        luck_list[8] = luck_list[8] + 1
                        if GetMyKohlrabi(user_id, group_id) != 0:
                            ChangeMyKohlrabi(user_id, group_id, 0)
                x.append(i + 1)
                y.append(now_point)
                update_value(
                    Ranking(user_id, group_id, int(now_point), int(time.time()), 1)
                )
                res = change_point(user_id, group_id, int(now_point))
                if not res:
                    now_level = get_level(user_id, group_id)
                    set_level(user_id, group_id, get_level(user_id, group_id) + 1)
                    await SayAndAt(
                        websocket,
                        user_id,
                        group_id,
                        f"爆分了！！！积分归零，积分等级:{now_level}->{now_level+1}。",
                    )
                    now_point = 0
                if now_point <= 0:
                    payload["params"]["message"].append(
                        {
                            "type": "text",
                            "data": {
                                "text": "{},抽奖统计如下：\n10倍奖:{}次\n8倍奖:{}次\n4倍奖:{}次\n2倍奖:{}次\n不变奖:{}次\n除2奖:{}次\n除4奖:{}次\n除8奖:{}次\n积分清零奖:{}次\n积分总额:{}->{}\n".format(
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
                                    start_point,
                                    now_point,
                                )
                            },
                        }
                    )
                    payload["params"]["message"].append(
                        {
                            "type": "text",
                            "data": {
                                "text": "富人上天堂比骆驼穿过针眼还难。十赌九输喵,赌狗好似喵。"
                            },
                        }
                    )
                    payload["params"]["message"].append(
                        {
                            "type": "image",
                            "data": {
                                "file": "base64://"
                                + open_chart_by_base64(x, y).decode("utf-8")
                            },
                        }
                    )
                    update_value(
                        Ranking(user_id, group_id, int(now_point), int(time.time()), 1)
                    )
                    await websocket.send(json.dumps(payload))
                    return
        payload["params"]["message"].append(
            {
                "type": "text",
                "data": {
                    "text": "{},抽奖统计如下：\n10倍奖:{}次\n8倍奖:{}次\n4倍奖:{}次\n2倍奖:{}次\n不变奖:{}次\n除2奖:{}次\n除4奖:{}次\n除8奖:{}次\n积分清零奖:{}次\n积分总额:{}->{}\n".format(
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
                    "file": "base64://" + open_chart_by_base64(x, y).decode("utf-8")
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
    update_value(Ranking(user_id, group_id, int(now_point), int(time.time()), 1))
    await websocket.send(json.dumps(payload))


# 抽奖函数
async def luck_choice_mut(
    websocket, user_id: int, sender_name: str, group_id: int, nums: int
):
    setting = load_setting("admin_group_main", 0)
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [],
        },
        "echo": "delete_message_list",
    }
    if group_id == setting:
        payload["params"]["message"].append(
            {
                "type": "text",
                "data": {
                    "text": "{},主群的抽奖权限关闭了喵,去分群吧,分区群号:{}。".format(
                        sender_name, load_setting("special_group", 0)
                    )
                },
            }
        )
        await websocket.send(json.dumps(payload))
        return
    luck_list = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    start_point = find_point(user_id)
    now_point = start_point
    if now_point >= 100000000:
        await luck_choice_mut_super_rich(
            websocket, user_id, sender_name, group_id, nums
        )
        return
    today_num, today = GetGamblingTimesToday(user_id, group_id)
    x = []
    y = []
    if today != GetNowDay():
        today = GetNowDay()
        today_num = 0
    if today_num <= load_setting("gambling_limit", 5000) and start_point >= 5:
        x.append(0)
        y.append(start_point)
        for i in range(nums):
            # now_point = bot_database.find_point(user_id)
            if now_point >= 5:
                add_gambling_times(user_id, 1)
                now_point = now_point - 5
                choice = random.choices(choice_list, choice_probability)
                if group_id not in load_setting("special_group", []):
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
                        if GetMyKohlrabi(user_id, group_id) != 0:
                            ChangeMyKohlrabi(user_id, group_id, 0)
                x.append(i + 1)
                y.append(now_point)
                now_point = int(now_point)
                change_point(user_id, group_id, now_point)
                update_value(Ranking(user_id, group_id, now_point, int(time.time()), 1))
                if now_point <= 0 or today_num > load_setting("gambling_limit", 5000):
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
                    if today_num > load_setting("gambling_limit", 5000):
                        payload["params"]["message"].append(
                            {
                                "type": "text",
                                "data": {
                                    "text": "今日已超过{}次,请明日再来喵。".format(
                                        load_setting("gambling_limit", 5000)
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
                                + open_chart_by_base64(x, y).decode("utf-8")
                            },
                        }
                    )
                    update_value(
                        Ranking(user_id, group_id, now_point, int(time.time()), 1)
                    )
                    if group_id not in load_setting("special_group", []):
                        ChangeGameblingTimesToday(user_id, group_id, today_num, today)
                    await websocket.send(json.dumps(payload))
                    return
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
                    "file": "base64://" + open_chart_by_base64(x, y).decode("utf-8")
                },
            }
        )
        if group_id not in load_setting("special_group", []):
            ChangeGameblingTimesToday(user_id, group_id, today_num, today)
    elif today_num > load_setting("gambling_limit", 5000):
        payload["params"]["message"].append(
            {
                "type": "text",
                "data": {
                    "text": "{},抽奖失败喵,今天已经超过{}次了喵。".format(
                        sender_name, load_setting("gambling_limit", 5000)
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
    update_value(Ranking(user_id, group_id, now_point, int(time.time()), 1))
    await websocket.send(json.dumps(payload))


# 发群低保
async def GivePoorPoint(websocket, user_id: int, group_id: int):
    sender_name = get_user_name(user_id, group_id)
    now_point = find_point(user_id)
    payload = {}
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
        if data[0][2] < 3 and is_today(time.time(), data[0][3]):
            cur.execute(
                "UPDATE poor SET times = ? WHERE user_id = ? AND group_id = ?;",
                (data[0][2] + 1, user_id, group_id),
            )
            conn.commit()
            change_point(user_id, group_id, 5)
            payload = {
                "action": "send_msg_async",
                "params": {
                    "group_id": group_id,
                    "message": "{},领取群低保成功喵，目前你的积分为:5。({}/3)".format(
                        sender_name, data[0][2] + 1
                    ),
                },
            }
            conn.close()
        elif data[0][2] >= 3 and is_today(time.time(), data[0][3]):
            payload = {
                "action": "send_msg_async",
                "params": {
                    "group_id": group_id,
                    "message": "{},领取群低保失败喵,领取群低保次数达到今日上限了喵,请明天再来喵。".format(
                        sender_name
                    ),
                },
            }
            conn.close()
        elif not is_today(time.time(), data[0][3]):
            cur.execute(
                "UPDATE poor SET times = ?,time=? WHERE user_id = ? AND group_id = ?;",
                (1, time.time(), user_id, group_id),
            )
            conn.commit()
            change_point(user_id, group_id, 5)
            payload = {
                "action": "send_msg_async",
                "params": {
                    "group_id": group_id,
                    "message": "{},领取群低保成功喵，目前你的积分为:5。(1/3)".format(
                        sender_name
                    ),
                },
            }
            conn.close()

    else:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": "{},你不符合群低保领取条件。".format(sender_name),
            },
        }

    await websocket.send(json.dumps(payload))


from tools.tools import FindNum


class PointApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("积分抽奖和群低保", "参与积分抽奖")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        if HasAllKeyWords(message.plainTextMessage, ["低保"]):
            await GivePoorPoint(
                message.websocket,
                message.senderId,
                message.groupId,
            )
        elif HasAllKeyWords(message.plainTextMessage, ["抽奖", "连"]):
            num = FindNum(message.plainTextMessage)
            if num > 1000:
                num = 1000
            elif num < 1:
                num = 1
            await luck_choice_mut(
                message.websocket,
                message.senderId,
                get_user_name(message.senderId, message.groupId),
                message.groupId,
                num,
            )
        else:
            await luck_choice_mut(
                message.websocket,
                message.senderId,
                get_user_name(message.senderId, message.groupId),
                message.groupId,
                1,
            )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]
        ) and (
            HasAllKeyWords(message.plainTextMessage, ["低保"])
            or HasAllKeyWords(message.plainTextMessage, ["抽奖", "连"])
        )
