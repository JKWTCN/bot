import base64
import enum
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


# class REPLY_IMAGE_MESSAGE_ERROR(enum):
#     SUCCESS = 0
#     UNREAD_IMAGE = 1


# 获取图片内容
async def getImageInfo(
    websocket, group_id: int, message_id: int, need_replay_message_id: int
):
    try:
        # 连接数据库
        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()
        # 执行查询
        cursor.execute(
            """
            SELECT raw_message 
            FROM group_message 
            WHERE message_id = ?
        """,
            (message_id,),
        )

        # 获取结果
        result = cursor.fetchone()

        if result:
            imageInfo = result[0]
            if imageInfo == "[图片]":
                await ReplySay(
                    websocket,
                    group_id,
                    need_replay_message_id,
                    "图片好像丢了喵,才不是乐可的疏忽喵,最好重新发送图片喵。",
                )
            else:
                await ReplySay(
                    websocket,
                    group_id,
                    need_replay_message_id,
                    imageInfo,
                )
        else:
            await ReplySay(
                websocket,
                group_id,
                need_replay_message_id,
                "此消息还在识别喵,请稍后再回复喵。",
            )

    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return None

    finally:
        # 确保连接被关闭
        if conn:
            conn.close()


# 强制回复图片消息
async def replyImageMessage(
    websocket, group_id: int, message_id: int, need_replay_message_id: int, text: str
):
    imageInfo = ""
    try:
        # 连接数据库
        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()
        # 执行查询
        cursor.execute(
            """
            SELECT raw_message 
            FROM group_message 
            WHERE message_id = ?
        """,
            (message_id,),
        )

        # 获取结果
        result = cursor.fetchone()

        if result:
            texts = []
            imageInfo = result[0]
            if imageInfo == "[图片]":
                await ReplySay(
                    websocket,
                    group_id,
                    need_replay_message_id,
                    "图片好像丢了喵,才不是乐可的疏忽喵,最好重新发送图片喵。",
                )
            else:
                texts.append(imageInfo)
                texts.append(text)
                await ReplySay(
                    websocket,
                    group_id,
                    need_replay_message_id,
                    chatNoContext(texts),
                )
        else:
            await ReplySay(
                websocket,
                group_id,
                need_replay_message_id,
                "此消息还在识别喵,请稍后再回复喵。",
            )

    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return None

    finally:
        # 确保连接被关闭
        if conn:
            conn.close()


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
                        "text": f"{get_user_name(user_id, group_id)},不要欺负机器人喵!"
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


# 哈气的回复
async def HuffingReplay(websocket, user_id: int, group_id: int, message_id: int):
    path = "res/huffing.gif"
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
    if get_config("group_decrease_reminder", group_id):
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
            f"{get_user_name(user_id, group_id)},梭哈成功,积分和大头菜翻10倍喵.",
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


from GroupConfig import get_config, set_config, manage_config


# 获取群聊是否开启冷群
def GetColdGroupStatus(group_id: int):
    if get_config("cold_group", group_id):
        return True
    else:
        return False


# 切换群聊是否开启冷群回复状态
def SwitchColdGroupChat(group_id: int):
    setting = load_setting()
    if group_id in get_config("cold_group", group_id):
        set_config("cold_group", False, group_id)
    else:
        set_config("cold_group", True, group_id)
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
                    f"{get_user_name(sender_id, group_id)},你的积分不足喵!当前积分为{sender_point}喵.",
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
                        f"爆分了!!!积分归零,积分等级:{now_level}->{now_level+1}.",
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
                f"艾特惩罚,剩余:{admin["num"]-1}次喵.",
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
            >= get_config("cold_group_time_out", int(group["group_id"]))
            and group["num"] > get_config("cold_group_num_out", int(group["group_id"]))
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

    nick_name = get_user_name(user_id, group_id)
    port = "11434"
    url = f"http://localhost:{port}/api/chat"
    model = load_setting()["model"]
    headers = {"Content-Type": "application/json"}

    # 获取上下文消息
    context_messages = get_chat_context(user_id, group_id)

    # 构建基础消息结构
    base_messages = [
        {
            "role": "system",
            "content": "你叫乐可,现在你将模仿一只傲娇并且温柔的猫娘(猫娘是一种拟人化的生物,其行为似猫但类人.),与我对话每一句话后面都要加上'喵'",
        },
        {
            "role": "user",
            "content": f"在{nick_name}说话前,群友们聊了{num}句,大家前面都聊的好火热,他一说话后大家就都不说话了,他可能今天过的不太好,赶紧鼓励鼓励他.",
        },
    ]

    # 添加上下文消息
    if context_messages:
        base_messages[1:1] = context_messages  # 在系统消息和用户消息之间插入上下文

    data = {
        "model": model,
        "options": {"temperature": 1.0},
        "stream": False,
        "messages": base_messages,
    }

    # 特殊模型处理
    if model == "qwen3:8b":
        for msg in data["messages"]:
            if msg["role"] == "system":
                msg["content"] = "/nothink " + msg["content"]
            elif msg["role"] == "user":
                msg["content"] = "/nothink " + msg["content"]

    try:
        response = requests.post(url, json=data, headers=headers, timeout=300)
        res = response.json()

        # 记录日志
        logger.info(
            "(AI)乐可在{}({})说:{}".format(
                GetGroupName(group_id), group_id, res["message"]["content"]
            )
        )

        if model != "deepseek-r1:1.5b" and model != "qwen3:8b":
            re_text = res["message"]["content"]
        else:
            match = re.findall(
                r"<think>([\s\S]*)</think>([\s\S]*)",
                res["message"]["content"],
            )
            if load_setting()["think_display"]:
                re_text = f"乐可的思考过程喵:{match[0][0]}经过深思熟虑喵,乐可决定回复你:{match[0][1]}"
            else:
                re_text = match[0][1]

        # 清理回复中的换行符
        while "\n" in re_text:
            re_text = re_text.replace("\n", "")

        return re_text
    except:
        logger.info("连接超时")
        return f"{nick_name},大家前面都聊的好好的,你一说话就冷群了喵."


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


# 只处理单句
def chatNoContext(texts):
    port = "11434"
    url = f"http://localhost:{port}/api/chat"
    model = load_setting()["model"]
    headers = {"Content-Type": "application/json"}

    # 构建基础消息结构
    base_messages = [
        {
            "role": "system",
            "content": "你叫乐可,现在你将模仿一只傲娇并且温柔的猫娘(猫娘是一种拟人化的生物,其行为似猫但类人.),与我对话每一句话后面都要加上'喵'",
        }
    ]
    for text in texts:
        base_messages.append(
            {
                "role": "user",
                "content": text,
            }
        )

    data = {
        "model": model,
        "options": {"temperature": 1.0},
        "stream": False,
        "messages": base_messages,
    }

    # 特殊模型处理
    if model == "qwen3:8b":
        for msg in data["messages"]:
            if msg["role"] == "system":
                msg["content"] = "/nothink " + msg["content"]
            elif msg["role"] == "user":
                msg["content"] = "/nothink " + msg["content"]

    try:
        print(data)
        response = requests.post(url, json=data, headers=headers, timeout=300)
        res = response.json()

        if model != "deepseek-r1:1.5b" and model != "qwen3:8b":
            re_text = res["message"]["content"]
        else:
            match = re.findall(
                r"<think>([\s\S]*)</think>([\s\S]*)",
                res["message"]["content"],
            )
            if load_setting()["think_display"]:
                re_text = f"乐可的思考过程喵:{match[0][0]}经过深思熟虑喵,乐可决定回复你:{match[0][1]}"
            else:
                re_text = match[0][1]
    except:
        logger.info("连接超时")
        re_text = "呜呜不太理解呢喵."

    # 清理回复中的换行符
    while "\n" in re_text:
        re_text = re_text.replace("\n", "")

    logger.info("(AI)乐可思考图片结果:{}".format(re_text))
    return re_text


async def chat(websocket, user_id: int, group_id: int, message_id: int, text: str):
    port = "11434"
    url = f"http://localhost:{port}/api/chat"
    model = load_setting()["model"]
    headers = {"Content-Type": "application/json"}

    # 获取上下文消息
    context_messages = get_chat_context(user_id, group_id)

    # 构建基础消息结构
    base_messages = [
        {
            "role": "system",
            "content": "你叫乐可,现在你将模仿一只傲娇并且温柔的猫娘(猫娘是一种拟人化的生物,其行为似猫但类人.),与我对话每一句话后面都要加上'喵'",
        }
    ]

    # 添加上下文消息
    if context_messages:
        base_messages.extend(context_messages)

    data = {
        "model": model,
        "options": {"temperature": 1.0},
        "stream": False,
        "messages": base_messages,
    }

    # 特殊模型处理
    if model == "qwen3:8b":
        for msg in data["messages"]:
            if msg["role"] == "system":
                msg["content"] = "/nothink " + msg["content"]
            elif msg["role"] == "user":
                msg["content"] = "/nothink " + msg["content"]

    try:
        print(data)
        response = requests.post(url, json=data, headers=headers, timeout=300)
        res = response.json()

        # 记录日志
        logger.info(
            "(AI)乐可在{}({})说:{}".format(
                GetGroupName(group_id), group_id, res["message"]["content"]
            )
        )

        if model != "deepseek-r1:1.5b" and model != "qwen3:8b":
            re_text = res["message"]["content"]
        else:
            match = re.findall(
                r"<think>([\s\S]*)</think>([\s\S]*)",
                res["message"]["content"],
            )
            if load_setting()["think_display"]:
                re_text = f"乐可的思考过程喵:{match[0][0]}经过深思熟虑喵,乐可决定回复你:{match[0][1]}"
            else:
                re_text = match[0][1]
    except:
        logger.info("连接超时")
        re_text = "呜呜不太理解呢喵."

    # 清理回复中的换行符
    while "\n" in re_text:
        re_text = re_text.replace("\n", "")

    if text != "":
        re_text += "\n\n" + text
    await ReplySay(websocket, group_id, message_id, re_text)


def get_chat_context(user_id: int, group_id: int, limit: int = 5) -> list:
    """从数据库中获取最近的聊天记录作为上下文"""
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()

    # 获取最近的几条聊天记录(包括用户和机器人的消息)
    cursor.execute(
        """
        SELECT sender_nickname, raw_message 
        FROM group_message 
        WHERE group_id = ? AND (user_id = ? OR user_id = ?)
        ORDER BY time DESC 
        LIMIT ?
    """,
        (group_id, user_id, load_setting().get("self_id", 0), limit),
    )

    messages = cursor.fetchall()
    conn.close()

    # 将消息转换为适合模型输入的格式
    context_messages = []
    for nickname, message in reversed(messages):
        role = "assistant" if nickname == "乐可" else "user"
        context_messages.append({"role": role, "content": message})

    return context_messages


def ReturnChatText(text: str, user_id: int, group_id: int):
    port = "11434"
    url = f"http://localhost:{port}/api/chat"
    model = load_setting()["model"]
    headers = {"Content-Type": "application/json"}

    # 获取上下文消息
    context_messages = get_chat_context(user_id, group_id)

    # 构建基础消息结构
    base_messages = [
        {
            "role": "system",
            "content": "你叫乐可,现在你将模仿一只傲娇并且温柔的猫娘(猫娘是一种拟人化的生物,其行为似猫但类人.),与我对话每一句话后面都要加上'喵'",
        }
    ]

    # 添加上下文消息
    if context_messages:
        base_messages.extend(context_messages)

    # 添加当前消息
    # base_messages.append(
    #     {
    #         "role": "user",
    #         "content": text,
    #     }
    # )

    data = {
        "model": model,
        "options": {"temperature": 1.0},
        "stream": False,
        "messages": base_messages,
    }
    # print(data)
    # 特殊模型处理
    if model == "qwen3:8b":
        for msg in data["messages"]:
            if msg["role"] == "system":
                msg["content"] = "/nothink " + msg["content"]
            elif msg["role"] == "user":
                msg["content"] = "/nothink " + msg["content"]

    try:
        response = requests.post(url, json=data, headers=headers, timeout=300)
        res = response.json()

        if model != "deepseek-r1:1.5b" and model != "qwen3:8b":
            re_text = res["message"]["content"]
        else:
            match = re.findall(
                r"<think>([\s\S]*)</think>([\s\S]*)",
                res["message"]["content"],
            )
            if load_setting()["think_display"]:
                re_text = f"乐可的思考过程喵:{match[0][0]}经过深思熟虑喵,乐可决定回复你:{match[0][1]}"
            else:
                re_text = match[0][1]
    except:
        logger.info("连接超时")
        re_text = "呜呜不太理解呢喵."

    # 清理回复中的换行符
    while "\n" in re_text:
        re_text = re_text.replace("\n", "")

    return re_text


# 切换模型
def switch_model():
    setting = load_setting()
    model = setting["model"]
    if model == "qwen2.5:0.5b":
        model = "deepseek-r1:1.5b"
    elif model == "deepseek-r1:1.5b":
        model = "qwen3:8b"
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
