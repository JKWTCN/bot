import base64
import json
import logging
import random
import re
import sqlite3
from venv import logger
import requests
import bot_database
from group_operate import GetGroupName, kick_member
from kohlrabi import ChangeMyKohlrabi, GetMyKohlrabi
from level import get_level, set_level
from tools import (
    HasKeyWords,
    SayAndAt,
    SayAndAtDefense,
    dump_setting,
    load_setting,
    say,
    ReplySay,
)
from Class.Group_member import get_user_name
import time


# 图片回复
async def SayImgReply(
    websocket, user_id: int, group_id: int, message_id: int, text: str, img_path: str
):
    with open(img_path, "rb") as image_file:
        image_data = image_file.read()
    image_base64 = base64.b64encode(image_data)
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": message_id}},
                {
                    "type": "text",
                    "data": {"text": text},
                },
                {
                    "type": "image",
                    "data": {"file": "base64://" + image_base64.decode("utf-8")},
                },
            ],
        },
    }
    await websocket.send(json.dumps(payload))


# 被欺负的回复
async def robot_reply(websocket, user_id: int, group_id: int, message_id: int):
    path = "res/robot.gif"
    with open(path, "rb") as image_file:
        image_data = image_file.read()
    image_base64 = base64.b64encode(image_data)
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": message_id}},
                {
                    "type": "text",
                    "data": {
                        "text": f"{get_user_name(user_id, group_id)},不要欺负机器人喵！"
                    },
                },
                {
                    "type": "image",
                    "data": {"file": "base64://" + image_base64.decode("utf-8")},
                },
            ],
        },
    }
    await websocket.send(json.dumps(payload))


# 无聊的回复
async def BoringReply(websocket, user_id: int, group_id: int, message_id: int):
    path = "res/boring.gif"
    with open(path, "rb") as image_file:
        image_data = image_file.read()
    image_base64 = base64.b64encode(image_data)
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": message_id}},
                {
                    "type": "image",
                    "data": {"file": "base64://" + image_base64.decode("utf-8")},
                },
            ],
        },
    }
    await websocket.send(json.dumps(payload))


# 飞起来的回复
async def FlyReply(websocket, user_id: int, group_id: int, message_id: int):
    path = "res/fly.gif"
    with open(path, "rb") as image_file:
        image_data = image_file.read()
    image_base64 = base64.b64encode(image_data)
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": message_id}},
                {
                    "type": "image",
                    "data": {"file": "base64://" + image_base64.decode("utf-8")},
                },
            ],
        },
    }
    await websocket.send(json.dumps(payload))


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
    conn.close()


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
        conn.close()
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
        conn.close()
        return 0
    else:
        conn.close()
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


# 赠送积分
async def GiveGift(
    websocket, sender_id: int, group_id: int, receiver_id: int, point: int
):
    sender_point = bot_database.find_point(sender_id)
    if sender_id != receiver_id:
        if point > 0:
            if point > sender_point:
                await say(
                    websocket,
                    group_id,
                    f"{get_user_name(sender_id, group_id)},你的积分不足喵!当前积分为{sender_point}喵。",
                )
            else:
                receiver_point = bot_database.find_point(receiver_id)
                bot_database.change_point(sender_id, group_id, sender_point - point)
                res = bot_database.change_point(
                    receiver_id, group_id, receiver_point + point
                )
                if not res:
                    now_level = get_level(receiver_id, group_id)
                    set_level(
                        receiver_id, group_id, get_level(receiver_id, group_id) + 1
                    )
                    await SayAndAt(
                        websocket,
                        receiver_id,
                        group_id,
                        f"爆分了！！！积分归零，积分等级:{now_level}->{now_level+1}。",
                    )
                await say(
                    websocket,
                    group_id,
                    f"{get_user_name(sender_id, group_id)}赠送{get_user_name(receiver_id, group_id)}{point}积分喵!",
                )
        else:
            await say(
                websocket,
                group_id,
                f"{get_user_name(sender_id, group_id)},赠送积分不能为负喵!",
            )
    else:
        await say(
            websocket,
            group_id,
            f"{get_user_name(sender_id, group_id)},不能给自己赠送积分喵!",
        )


# 删除特定惩罚
def DelAtPunish(user_id: int, group_id: int):
    setting = load_setting()
    del_index = -1
    for i, admin in enumerate(setting["bleak_admin"]):
        if admin["user_id"] == user_id and admin["group_id"] == group_id:
            del_index = i
    del setting["bleak_admin"][del_index]
    dump_setting(setting)


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
            SetColdGroupTimes(
                group["user_id"],
                group["group_id"],
                GetColdGroupTimes(group["user_id"], group["group_id"]) + 1,
            )
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
    model = load_setting()["model"]
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
                "content": f"在{nick_name}说话前,群友们聊了{num}句,他说的上一句话是:{raw_message},大家前面都聊的好火热,他一说话后大家就都不说话了,他可能今天过的不太好,赶紧鼓励鼓励他。",
            },
        ],
    }
    try:
        response = requests.post(url, json=data, headers=headers, timeout=300)
        res = response.json()
        logger.info(
            "(AI)乐可在{}({})说:{}".format(
                GetGroupName(group_id), group_id, res["message"]["content"]
            )
        )
        if model != "deepseek-r1:1.5b":
            re_text = res["message"]["content"]
        else:
            match = re.findall(
                r"<think>([\s\S]*)</think>([\s\S]*)",
                res["message"]["content"],
            )
            if load_setting()["think_display"]:
                re_text = f"乐可的思考过程喵：{match[0][0]}经过深思熟虑喵，乐可决定回复你：{match[0][1]}"
            else:
                re_text = match[0][1]
        return re_text
    except:
        logger.info("连接超时")
        return f"{nick_name},大家前面都聊的好好的,你一说话就冷群了喵。"


# 多线程chat内容转发给大模型
def chat_thread(websocket, user_id: int, group_id: int, message_id: int, text: str):
    import threading

    try:
        t = threading.Thread(
            target=chat, args=(websocket, user_id, group_id, message_id, text, 120)
        )
        t.start()
    except:
        logger.info("多线程创建失败")


# chat内容转发给大模型
async def chat(websocket, user_id: int, group_id: int, message_id: int, text: str):
    port = "11434"
    url = f"http://localhost:{port}/api/chat"
    model = load_setting()["model"]
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
        response = requests.post(url, json=data, headers=headers, timeout=300)
        res = response.json()
        logger.info(
            "(AI)乐可在{}({})说:{}".format(
                GetGroupName(group_id), group_id, res["message"]["content"]
            )
        )
        if model != "deepseek-r1:1.5b":
            re_text = res["message"]["content"]
        else:
            match = re.findall(
                r"<think>([\s\S]*)</think>([\s\S]*)",
                res["message"]["content"],
            )
            if load_setting()["think_display"]:
                re_text = f"乐可的思考过程喵：{match[0][0]}经过深思熟虑喵，乐可决定回复你：{match[0][1]}"
            else:
                re_text = match[0][1]

    except:
        logger.info("连接超时")
        re_text = "呜呜不太理解呢喵。"
    await ReplySay(
        websocket,
        group_id,
        message_id,
        "{},{}".format(get_user_name(user_id, group_id), re_text),
    )


# chat内容转发给大模型
def ReturnChatText(text: str):
    port = "11434"
    url = f"http://localhost:{port}/api/chat"
    model = load_setting()["model"]
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
        response = requests.post(url, json=data, headers=headers, timeout=300)
        res = response.json()
        if model != "deepseek-r1:1.5b":
            re_text = res["message"]["content"]
        else:
            match = re.findall(
                r"<think>([\s\S]*)</think>([\s\S]*)",
                res["message"]["content"],
            )
            if load_setting()["think_display"]:
                re_text = f"乐可的思考过程喵：{match[0][0]}经过深思熟虑喵，乐可决定回复你：{match[0][1]}"
            else:
                re_text = match[0][1]
    except:
        logger.info("连接超时")
        re_text = "呜呜不太理解呢喵。"
    return re_text


# 切换模型
def switch_model():
    setting = load_setting()
    model = setting["model"]
    if model == "qwen2.5:0.5b":
        model = "deepseek-r1:1.5b"
    else:
        model = "qwen2.5:0.5b"
    setting["model"] = model
    dump_setting(setting)
    return model


# 显示思考过程
def display_think():
    setting = load_setting()
    think = setting["think_display"]
    if think == True:
        think = False
    else:
        think = True
    setting["think_display"] = think
    dump_setting(setting)
    return think


# ollama run qwen2.5:0.5b
# ollama run deepseek-r1:1.5b
