import json
import random
import sqlite3
from venv import logger
import requests
import bot_database
from group_operate import GetGroupName, kick_member
from kohlrabi import ChangeMyKohlrabi, GetMyKohlrabi
from tools import (
    HasKeyWords,
    SayAndAtDefense,
    dump_setting,
    load_setting,
    say,
    ReplySay,
)
from Class.Group_member import get_user_name
import time


# 设置冷群王次数
def SetColdGroupTimes(user_id: int, group_id: int, times: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE cold_group_times SET times=? where user_id=? and group_id=?",
        (
            times,
            user_id,
            group_id,
        ),
    )
    conn.commit()


# 获取冷群王次数
def GetColdGroupTimes(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT times FROM cold_group_times where user_id=? and group_id=?;",
            (user_id, group_id),
        )
    except sqlite3.OperationalError:
        logger.info("数据库表不存在,正在创建表cold_group_times")
        cur.execute(
            "CREATE TABLE cold_group_times ( user_id  INTEGER, group_id INTEGER, times INTEGER ); "
        )
        conn.commit()
        cur.execute(
            "SELECT times FROM cold_group_times where user_id=? and group_id=?;",
            (user_id, group_id),
        )
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO cold_group_times (user_id,group_id,times ) VALUES (?,?,?);",
            (user_id, group_id, 1),
        )
        conn.commit()
        conn.close()
        return 0
    else:
        return data[0][0]


# 获取群聊是否开启退群提醒
def GetGroupDecreaseMessageStatus(group_id: int):
    setting = load_setting()
    if group_id in setting["group_decrease_reply_list"]:
        return True
    else:
        return False


# 梭哈或者跑路
async def run_or_shot(websocket, user_id, group_id):
    list = [0, 1]
    _ = random.choice(list)
    if _ == 0:
        __ = random.choice(list)
        if __ == 0:
            await say(
                websocket,
                group_id,
                f"{get_user_name(user_id, group_id)},梭哈失败,跑路失败喵!(清空全部积分和大头菜并施加100次艾特惩罚)",
            )
            if GetMyKohlrabi(user_id, group_id) != 0:
                ChangeMyKohlrabi(user_id, group_id, 0)
            bot_database.change_point(
                user_id, group_id, bot_database.find_point(user_id) * 0
            )
            AddAtPunishList(user_id, group_id, 100)
        else:
            await say(
                websocket,
                group_id,
                f"{get_user_name(user_id, group_id)},梭哈失败,跑路成功喵!(清空全部积分和大头菜,踢了!?)",
            )
            if GetMyKohlrabi(user_id, group_id) != 0:
                ChangeMyKohlrabi(user_id, group_id, 0)
            bot_database.change_point(
                user_id, group_id, bot_database.find_point(user_id) * 0
            )
    else:
        await say(
            websocket,
            group_id,
            f"{get_user_name(user_id, group_id)},梭哈成功,积分和大头菜翻10倍喵。",
        )
        bot_database.change_point(
            user_id, group_id, bot_database.find_point(user_id) * 10
        )
        ChangeMyKohlrabi(user_id, group_id, GetMyKohlrabi(user_id, group_id) * 10)


# 切换群聊是否开启退群提醒
def SwitchGroupDecreaseMessage(group_id: int):
    setting = load_setting()
    if group_id in setting["group_decrease_reply_list"]:
        setting["group_decrease_reply_list"].remove(group_id)
    else:
        setting["group_decrease_reply_list"].append(group_id)
    dump_setting(setting)


# 获取群聊是否开启冷群
def GetColdGroupStatus(group_id: int):
    setting = load_setting()
    if group_id in setting["need_cold_reply_list"]:
        return True
    else:
        return False


# 切换群聊是否开启冷群回复状态
def SwitchColdGroupChat(group_id: int):
    setting = load_setting()
    if group_id in setting["need_cold_reply_list"]:
        setting["need_cold_reply_list"].remove(group_id)
    else:
        setting["need_cold_reply_list"].append(group_id)
    dump_setting(setting)


# 查找艾特开发者的次数
def GetWhoAtMe(user_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT nums FROM who_at_me where user_id=?;", (user_id,))
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute("INSERT INTO who_at_me (user_id,nums) VALUES (?,?);", (user_id, 0))
        conn.commit()
        return 0
    else:
        return data[0][0]


# 增加数据库中艾特开发者的次数
def AddWhoAtMe(user_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    now_num = GetWhoAtMe(user_id)
    cur.execute(
        "UPDATE who_at_me SET nums = ? WHERE user_id = ?;",
        (
            now_num + 1,
            user_id,
        ),
    )
    conn.commit()
    conn.close()


# 删除特定惩罚
def DelAtPunish(user_id: int, group_id: int):
    setting = load_setting()
    for index, admin in enumerate(setting["bleak_admin"]):
        if admin["user_id"] == user_id and admin["group_id"] == group_id:
            del setting["bleak_admin"][index]
            dump_setting(setting)
            return


# 添加惩罚名单
def AddAtPunishList(user_id: int, group_id: int, num: int):
    setting = load_setting()
    for admin in setting["bleak_admin"]:
        if admin["user_id"] == user_id and admin["group_id"] == group_id:
            admin["num"] += 10
            dump_setting(setting)
            return
    setting["bleak_admin"].append(
        {
            "user_id": user_id,
            "group_id": group_id,
            "num": num,
        }
    )
    dump_setting(setting)


# 艾特惩罚
async def AtPunish(websocket):
    setting = load_setting()
    i: int = 0
    del_list = []
    for admin in setting["bleak_admin"]:
        if admin["num"] <= 0:
            del_list.append(i)
            i += 1
        else:
            await SayAndAtDefense(
                websocket,
                admin["user_id"],
                admin["group_id"],
                f"艾特惩罚,剩余:{admin["num"]-1}次喵。",
            )
            admin["num"] -= 1
            i += 1
    for i in del_list:
        del setting["bleak_admin"][i]
    dump_setting(setting)


# 讲笑话
async def Joke(websocket, group_id):
    r = requests.get("https://api.vvhan.com/api/text/joke")
    print(r.text)
    await say(websocket, group_id, r.text)


# 更新冷群状态
def UpdateColdGroup(user_id: int, group_id: int, message_id: int, raw_message: str):
    setting = load_setting()
    for index, group in enumerate(setting["cold_group_king"]):
        if group["group_id"] == group_id:
            setting["cold_group_king"][index]["user_id"] = user_id
            setting["cold_group_king"][index]["message_id"] = message_id
            setting["cold_group_king"][index]["time"] = time.time()
            setting["cold_group_king"][index]["is_replay"] = False
            setting["cold_group_king"][index]["num"] += 1
            setting["cold_group_king"][index]["raw_message"] = raw_message
            dump_setting(setting)
            SetColdGroupTimes(
                user_id, group_id, GetColdGroupTimes(user_id, group_id) + 1
            )
            return
    setting["cold_group_king"].append(
        {
            "group_id": group_id,
            "user_id": user_id,
            "message_id": message_id,
            "time": time.time(),
            "is_replay": False,
            "num": 0,
            "raw_message": raw_message,
        }
    )
    SetColdGroupTimes(user_id, group_id, GetColdGroupTimes(user_id, group_id) + 1)
    dump_setting(setting)


# 检测是否冷群并回复
async def ColdReplay(websocket):
    setting = load_setting()
    for index, group in enumerate(setting["cold_group_king"]):
        # logger.info(f"before:{group}")
        if (
            group["is_replay"] == False
            and time.time() - group["time"]
            >= setting["cold_group_king_setting"]["time_out"]
            and group["num"] > setting["cold_group_king_setting"]["num_out"]
            and group["user_id"] not in setting["other_bots"]
            and GetColdGroupStatus(group["group_id"])
        ):
            setting["cold_group_king"][index]["is_replay"] = True
            setting["cold_group_king"][index]["num"] = 0
            dump_setting(setting)
            # logger.info(f"after:{group}")
            # name = get_user_name(group["user_id"], group["group_id"])
            await ReplySay(
                websocket,
                group["group_id"],
                group["message_id"],
                ColdChat(group),
            )


# chat内容转发给大模型
def ColdChat(group: dict) -> str:
    user_id = group["user_id"]
    group_id = group["group_id"]
    num = group["num"]
    raw_message = group["raw_message"]
    if HasKeyWords(
        raw_message,
        [
            "[CQ:image",
        ],
    ):
        raw_message = ""
    nick_name = get_user_name(user_id, group_id)
    port = "11434"
    url = f"http://localhost:{port}/api/chat"
    model = "qwen2.5:0.5b"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": model,  # 模型选择
        "options": {
            "temperature": 1.0  # 为0表示不让模型自由发挥，输出结果相对较固定，>0的话，输出的结果会比较放飞自我
        },
        "stream": False,  # 流式输出
        "messages": [
            {
                "role": "system",
                "content": "你叫乐可，现在你将模仿一只傲娇的猫娘(猫娘是一种拟人化的生物，其行为似猫但类人。)，与我对话每一句话后面都要加上“喵”",
            },
            {
                "role": "User",
                "content": f"在{nick_name}说话前,群友们聊了{num}句,他说的上一句话是:{raw_message},大家前面都聊的好火热,他一说话后大家就都不说话了,快狠狠地嘲笑嘲笑他。",
            },
        ],
    }
    try:
        response = requests.post(url, json=data, headers=headers, timeout=60)
        res = response.json()
        logger.info(
            "(AI)乐可在{}({})说:{}".format(
                GetGroupName(group_id), group_id, res["message"]["content"]
            )
        )
        return res["message"]["content"]
    except:
        logger.info("连接超时")
        return f"{nick_name},大家前面都聊的好好的,你一说话就冷群了喵。"


# chat内容转发给大模型
async def chat(websocket, group_id: int, nick_name: str, text: str):
    port = "11434"
    url = f"http://localhost:{port}/api/chat"
    model = "qwen2.5:0.5b"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": model,  # 模型选择
        "options": {
            "temperature": 1.0  # 为0表示不让模型自由发挥，输出结果相对较固定，>0的话，输出的结果会比较放飞自我
        },
        "stream": False,  # 流式输出
        "messages": [
            {
                "role": "system",
                "content": "你叫乐可，现在你将模仿一只傲娇的猫娘(猫娘是一种拟人化的生物，其行为似猫但类人。)，与我对话每一句话后面都要加上“喵”",
            },
            {
                "role": "User",
                "content": text,
            },
        ],
    }
    try:
        response = requests.post(url, json=data, headers=headers, timeout=30)
        res = response.json()
        logger.info(
            "(AI)乐可在{}({})说:{}".format(
                GetGroupName(group_id), group_id, res["message"]["content"]
            )
        )
        re_text = res["message"]["content"]

    except:
        logger.info("连接超时")
        re_text = "呜呜不太理解呢喵。"
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": "{},{}".format(nick_name, re_text),
        },
    }
    await websocket.send(json.dumps(payload))


# ollama run qwen2.5:0.5b
