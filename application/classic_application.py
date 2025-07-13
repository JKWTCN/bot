import base64
from datetime import datetime
import json
import logging
import random
import re
import sqlite3
import time
import uuid

import requests
from data.message.group_message_info import GroupMessageInfo
from data.application.application_info import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from data.enumerates import ApplicationCostType

from data.message.message_info import MessageInfo
from function.say import SayGroup, ReplySay
from function.datebase_user import IsAdmin, get_user_name
from function.GroupConfig import manage_config, GroupConfigError
from function.ranking import update_value, Ranking


# 群签到功能
def check_in(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM user_point where user_id=?", (user_id,))
    data = cur.fetchall()
    now_point = -1
    now_time = 0
    # print(len(data))
    if len(data) == 0:
        update_value(Ranking(user_id, group_id, 0, int(time.time()), 1))
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
        update_value(Ranking(user_id, group_id, now_point, int(time.time()), 1))
        return (1, now_point)
    else:
        conn.close()
        return (0, now_point)


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


class CheckInApplication(GroupMessageApplication):

    def __init__(self):
        applicationInfo = ApplicationInfo("签到应用", "签到功能")
        super().__init__(applicationInfo, 65, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        """处理消息"""
        await daily_check_in(
            message.websocket,
            message.senderId,
            get_user_name(message.senderId, message.groupId),
            message.groupId,
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        return "签到" in message.plainTextMessage


# 大清洗功能
from data.message.meta_message_info import MetaMessageInfo
from data.application.meta_application import MetaMessageApplication
from data.enumerates import MessageType, MetaEventType
from tools.tools import load_setting, dump_setting
from function.datebase_user import Group_member, BotIsAdmin, updata_user_info
from function.GroupConfig import get_config, manage_config
from function.database_group import GetGroupName
from function.group_operation import kick_member


# 发送获取群名单
def get_group_list(websocket):
    url = "http://localhost:27433/get_group_list"
    resp = requests.post(url)
    data = resp.json()
    return data["data"]


# 发送更新群成员名单
def update_group_member_list(websocket, group_id: int):
    import json

    url = "http://localhost:27433/get_group_member_list"
    payload = {"group_id": group_id}
    resp = requests.post(url)
    data = resp.json()
    return data["data"]


# 更新群列表
def update_group_info(
    group_id: int, group_name: str, member_count: int, max_member_count: int
):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM group_info where group_id=?;",
        (group_id,),
    )
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO group_info (group_id,group_name,member_count,max_member_count)VALUES (?,?,?,?);",
            (group_id, group_name, member_count, max_member_count),
        )
        conn.commit()
        conn.close()
    else:
        cur.execute(
            "UPDATE group_info SET group_name = ?,member_count=?,max_member_count=? WHERE group_id = ?;",
            (
                group_name,
                member_count,
                max_member_count,
                group_id,
            ),
        )
        conn.commit()
        conn.close()


class GreatPurgeApplication(MetaMessageApplication):
    """定时刷新群成员数据库应用类
    该类用于定时刷新群成员数据库
    该类继承自MetaMessageApplication基类,并实现了处理元消息的抽象方法.
    """

    def __init__(self):
        applicationInfo = ApplicationInfo(
            "定时刷新群成员数据库", "定时刷新群成员数据库"
        )
        super().__init__(
            applicationInfo, 50, True, ApplicationCostType.HIGH_TIME_LOW_PERFORMANCE
        )

    async def process(self, message: MetaMessageInfo):
        """处理元消息"""
        if time.time() - load_setting("last_update_time", 0) > 300:
            data = get_group_list(message.websocket)
            print("开始更新群列表")
            logging.info("开始更新群列表")
            for group in data:
                logging.info(f"正在更新群:{group["group_name"]}({group["group_id"]})")
                update_group_info(
                    group["group_id"],
                    group["group_name"],
                    group["member_count"],
                    group["max_member_count"],
                )
                _setting = load_setting("group_list", [])
                if group["group_id"] not in _setting:
                    _setting.append(group["group_id"])
                    dump_setting("group_list", _setting)
                    new_data = update_group_member_list(
                        message.websocket, group["group_id"]
                    )
                    for group_member in new_data:
                        user = Group_member()
                        user.init_by_dict(group_member)
                        updata_user_info(user)
                        group_id = user.group_id
                        name = get_user_name(user.user_id, user.group_id)
                        if get_config("kick_time_sec", user.group_id) != -1:
                            timeout = get_config("kick_time_sec", user.group_id)
                            if (
                                int(time.time()) - user.last_sent_time > timeout  # type: ignore
                                and BotIsAdmin(user.group_id)
                                and timeout != -1
                                and timeout >= 30 * 24 * 3600  # type: ignore
                            ):
                                if not IsAdmin(user.user_id, user.group_id):
                                    print(
                                        "{}({})因{}个月未活跃被请出群聊{}({}),最后发言时间:{}".format(
                                            name,
                                            user.user_id,
                                            timeout / 2592000,  # type: ignore
                                            GetGroupName(user.group_id),
                                            user.group_id,
                                            time.strftime(
                                                "%Y-%m-%d %H:%M:%S",
                                                time.localtime(user.last_sent_time),
                                            ),
                                        )
                                    )
                                    logging.info(
                                        "{}({})因{}个月未活跃被请出群聊{}({}),最后发言时间:{}".format(
                                            name,
                                            user.user_id,
                                            timeout / 2592000,  # type: ignore
                                            GetGroupName(user.group_id),
                                            user.group_id,
                                            time.strftime(
                                                "%Y-%m-%d %H:%M:%S",
                                                time.localtime(user.last_sent_time),
                                            ),
                                        )
                                    )
                                    await SayGroup(
                                        message.websocket,
                                        user.group_id,
                                        "{}({})，乐可要踢掉你了喵！\n原因:{}个月未活跃。\n最后发言时间为:{}".format(
                                            name,
                                            user.user_id,
                                            timeout / 2592000,  # type: ignore
                                            time.strftime(
                                                "%Y-%m-%d %H:%M:%S",
                                                time.localtime(user.last_sent_time),
                                            ),
                                        ),
                                    )
                                    await kick_member(
                                        message.websocket, user.user_id, user.group_id
                                    )

                _setting = load_setting("last_update_time", 0)
                _setting = time.time()
                dump_setting("last_update_time", _setting)
                print("更新全部群列表完毕")
                logging.info("更新全部群列表完毕")

    def judge(self, message: MetaMessageInfo) -> bool:
        """判断是否触发应用"""
        return message.metaEventType == MetaEventType.HEART_BEAT


# 管理员随机派发水群积分应用
from function.datebase_other import find_point, change_point
from tools.tools import GetNowDay


# 发送水群积分
def SendRewards(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT all_num,today_num,today FROM chat_rewards where user_id=? and group_id=?;",
        (
            user_id,
            group_id,
        ),
    )
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO chat_rewards (user_id,group_id,all_num,today_num,today)\
                VALUES (?,?,?,?,?);",
            (user_id, group_id, 0, 0, GetNowDay()),
        )
        conn.commit()
        cur.execute(
            "SELECT all_num,today_num,today FROM chat_rewards where user_id=? and group_id=?;",
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
        "UPDATE chat_rewards SET all_num = ?,today_num = ?,today = ?\
            WHERE user_id = ? AND group_id = ?;",
        (all_num, today_num, today, user_id, group_id),
    )
    conn.commit()
    conn.close()
    return (all_num, today_num)


class RandomWaterGroupPointsApplication(GroupMessageApplication):
    """随机派发水群积分应用"""

    def __init__(self):
        applicationInfo = ApplicationInfo(
            "随机派发水群积分应用", "是管理员时,会随机派发水群积分应用"
        )
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        user_id = message.senderId
        group_id = message.groupId
        websocket = message.websocket
        now_point = find_point(user_id)
        change_point(
            user_id,
            group_id,
            now_point + 50,
        )
        all_num, today_num = SendRewards(user_id, group_id)
        sender_name = get_user_name(user_id, group_id)
        await SayGroup(
            websocket,
            group_id,
            f"恭喜群友{sender_name}获得乐可派发的水群积分！积分{now_point}->{now_point + 50}。\n总共:{all_num}次,今日:{today_num}次",
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return BotIsAdmin(message.groupId) and random.random() < 0.02


# todo 无聊功能合集
# todo 哈气，装，打，GAY [AT管理]
from tools.tools import HasKeyWords, HasAllKeyWords, HasBotName
from function.datebase_user import IsDeveloper


# 删除特定惩罚
def DelAtPunish(user_id: int, group_id: int):
    setting = load_setting("bleak_admin", [])
    del_index = -1
    for i, admin in enumerate(setting):
        if admin["user_id"] == user_id and admin["group_id"] == group_id:
            del_index = i
    del setting[del_index]
    dump_setting("bleak_admin", setting)


# 添加惩罚名单
def AddAtPunishList(user_id: int, group_id: int, num: int):
    setting = load_setting("bleak_admin", [])
    for admin in setting:
        if admin["user_id"] == user_id and admin["group_id"] == group_id:
            admin["num"] += 10
            dump_setting("bleak_admin", setting)
            return
    setting.append(
        {
            "user_id": user_id,
            "group_id": group_id,
            "num": num,
        }
    )
    dump_setting("bleak_admin", setting)


async def SayAndAtDefense(websocket, user_id: int, group_id: int, text: str):
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {"type": "text", "data": {"text": " " + text}},
            ],
        },
        "echo": "defense",
    }
    await websocket.send(json.dumps(payload))


# 艾特惩罚
async def AtPunish(websocket):
    setting = load_setting("bleak_admin", [])
    i: int = 0
    del_list = []
    for admin in setting:
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
        del setting[i]
    dump_setting("bleak_admin", setting)


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


class BoringFeatureCollectionManageApplication(GroupMessageApplication):
    """无聊功能管理合集"""

    def __init__(self):
        applicationInfo = ApplicationInfo(
            "无聊功能管理合集", "提供一些无聊的管理功能,哈气、装、打、GAY等"
        )
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        raw_message = message.plainTextMessage
        user_id = message.senderId
        group_id = message.groupId
        websocket = message.websocket
        for at_id in message.atList:
            if HasKeyWords(raw_message, ["你是GAY", "你是gay"]) and IsAdmin(
                user_id, group_id
            ):
                if at_id not in load_setting("boring", []):
                    _setting = load_setting("boring", [])
                    _setting.append(at_id)
                    dump_setting("boring", _setting)
                    await SayGroup(
                        websocket,
                        group_id,
                        f"{get_user_name(at_id, group_id)},GAY追杀令喵!!!!",
                    )
            elif HasKeyWords(raw_message, ["你不是GAY", "你不是gay"]) and IsAdmin(
                user_id, group_id
            ):
                _setting = load_setting("boring", [])
                while at_id in load_setting("boring", []):
                    _setting.remove(at_id)
                dump_setting("boring", _setting)
                await SayGroup(
                    websocket,
                    group_id,
                    f"{get_user_name(at_id, group_id)},GAY追杀令取消了喵。",
                )
            elif HasKeyWords(raw_message, ["不要哈气"]) and IsAdmin(user_id, group_id):
                _setting = load_setting("huffing", [])
                while at_id in load_setting("huffing", []):
                    _setting.remove(at_id)
                dump_setting("huffing", _setting)
                await SayGroup(
                    websocket,
                    group_id,
                    f"{get_user_name(at_id, group_id)},乐可停止追杀你了喵！",
                )
            elif HasKeyWords(raw_message, ["哈气"]) and IsAdmin(user_id, group_id):
                _setting = load_setting("huffing", [])
                if at_id not in _setting:
                    _setting.append(at_id)
                    dump_setting("huffing", _setting)
                await SayGroup(
                    websocket,
                    group_id,
                    f"{get_user_name(at_id, group_id)},乐可要追杀你了喵！",
                )
            elif HasKeyWords(
                raw_message,
                [
                    "不要装",
                ],
            ) and IsAdmin(user_id, group_id):
                _setting = load_setting("fly", [])
                if at_id not in _setting:
                    _setting.append(at_id)
                    dump_setting("fly", _setting)
                await SayGroup(
                    websocket,
                    group_id,
                    f"{get_user_name(at_id, group_id)},不要再装了喵。",
                )
            elif HasKeyWords(
                raw_message,
                [
                    "可以装",
                ],
            ) and IsAdmin(user_id, group_id):
                while at_id in load_setting("fly", []):
                    _setting.remove(at_id)
                dump_setting("fly", _setting)
                await SayGroup(
                    websocket,
                    group_id,
                    f"{get_user_name(at_id, group_id)},可以开始装了喵。",
                )
            elif (
                HasKeyWords(raw_message, ["打他", "打它", "打她"])
                and (user_id != at_id or IsDeveloper(user_id))
                and IsAdmin(user_id, group_id)
            ):
                AddAtPunishList(
                    at_id,
                    group_id,
                    load_setting("defense_times", 100),
                )
                await SayGroup(
                    websocket,
                    group_id,
                    f"{get_user_name(user_id, group_id)},乐可要开始打你了喵！",
                )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return len(message.atList) != 0


class BoringFeatureCollectionApplication(GroupMessageApplication):
    """无聊功能触发合集(除艾特惩罚)"""

    def __init__(self):
        applicationInfo = ApplicationInfo("无聊功能合集", "提供一些无聊的功能")
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        # 真的是有够无聊
        user_id = message.senderId
        group_id = message.groupId
        websocket = message.websocket
        message_id = message.messageId
        if user_id in load_setting("boring", []):
            await BoringReply(websocket, user_id, group_id, message_id)
        if user_id in load_setting("huffing", []):
            await HuffingReplay(websocket, user_id, group_id, message_id)
        if user_id in load_setting("fly", []):
            await FlyReply(websocket, user_id, group_id, message_id)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return True


class AtPunishApplication(MetaMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("艾特惩罚", "对艾特的惩罚")
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    def judge(self, message: MessageInfo) -> bool:
        return True

    async def process(self, message: MetaMessageInfo):
        await AtPunish(message.websocket)


class BeTeasedApplication(GroupMessageApplication):
    """被欺负应用"""

    def __init__(self):
        applicationInfo = ApplicationInfo(
            "被欺负的回应", "当有人欺负乐可时,乐可会回应", False
        )
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        path = "res/robot.gif"
        group_id = message.groupId
        user_id = message.senderId
        websocket = message.websocket
        message_id = message.messageId
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
                            "data": {
                                "file": "base64://" + image_base64.decode("utf-8")
                            },
                        },
                    ],
                },
            }
        await websocket.send(json.dumps(payload))

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return (
            HasAllKeyWords(message.plainTextMessage, ["乐可"])
            and HasKeyWords(
                message.plainTextMessage,
                ["sb", "SB", "傻逼", "透透", "透", "打你", "艹"],
            )
            and HasBotName(message.plainTextMessage)
        )


from function.group_operation import ban_new


# 获取积分等级
def get_level(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT level FROM level where user_id=? and group_id=?;",
            (user_id, group_id),
        )
    except sqlite3.OperationalError:
        logging.info("数据库表不存在,level")
        cur.execute(
            "CREATE TABLE level ( user_id  INTEGER, group_id INTEGER, level INTEGER ); "
        )
        conn.commit()
        cur.execute(
            "SELECT level FROM level where user_id=? and group_id=?;",
            (user_id, group_id),
        )
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO level (user_id,group_id,level ) VALUES (?,?,?);",
            (user_id, group_id, 0),
        )
        conn.commit()
        conn.close()
        return 0
    else:
        conn.close()
        return data[0][0]


# 设置积分等级
def set_level(user_id: int, group_id: int, level: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE level SET level=? where user_id=? and group_id=?",
        (
            level,
            user_id,
            group_id,
        ),
    )
    conn.commit()
    conn.close()


from function.say import SayAndAt


# 赠送积分
async def GiveGift(
    websocket, sender_id: int, group_id: int, receiver_id: int, point: int
):
    sender_point = find_point(sender_id)
    if sender_id != receiver_id:
        if point > 0:
            if point > sender_point:
                await SayGroup(
                    websocket,
                    group_id,
                    f"{get_user_name(sender_id, group_id)},你的积分不足喵!当前积分为{sender_point}喵.",
                )
            else:
                receiver_point = find_point(receiver_id)
                change_point(sender_id, group_id, sender_point - point)
                res = change_point(receiver_id, group_id, receiver_point + point)
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
                await SayGroup(
                    websocket,
                    group_id,
                    f"{get_user_name(sender_id, group_id)}赠送{get_user_name(receiver_id, group_id)}{point}积分喵!",
                )
        else:
            await SayGroup(
                websocket,
                group_id,
                f"{get_user_name(sender_id, group_id)},赠送积分不能为负喵!",
            )
    else:
        await SayGroup(
            websocket,
            group_id,
            f"{get_user_name(sender_id, group_id)},不能给自己赠送积分喵!",
        )


# 艾特管理功能大合集
class AtManagementApplication(GroupMessageApplication):
    """艾特管理功能大合集"""

    def __init__(self):
        applicationInfo = ApplicationInfo("艾特管理功能大合集", "提供一些艾特管理功能")
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        # 处理消息
        user_id = message.senderId
        group_id = message.groupId
        websocket = message.websocket
        raw_message = message.plainTextMessage
        for at_id in message.atList:
            rev_name = get_user_name(at_id, group_id)
            sender_name = get_user_name(user_id, group_id)
            if BotIsAdmin(group_id):
                if "解除禁言" in raw_message:
                    logging.info(
                        f"{group_id}:{sender_name}({user_id})解除禁言了{rev_name}({at_id})"
                    )
                    await ban_new(websocket, at_id, group_id, 0)

                elif "禁言" in raw_message:
                    logging.info(
                        f"{group_id}:{sender_name}({user_id})禁言了{rev_name}({at_id})"
                    )
                    await ban_new(websocket, at_id, group_id, 1800)

                elif "说再见" in raw_message:
                    if not IsAdmin(user_id, group_id):
                        logging.info(
                            f"{group_id}:{sender_name}({user_id})踢出了{rev_name}({at_id})"
                        )
                        await kick_member(websocket, at_id, group_id)

                elif HasKeyWords(raw_message, ["晋升"]) and IsDeveloper(user_id):
                    set_level(
                        at_id,
                        group_id,
                        get_level(at_id, group_id) + 1,
                    )
                    change_point(at_id, group_id, 0)
                    await SayGroup(
                        websocket,
                        group_id,
                        f"晋升成功,{get_user_name(at_id,group_id)}({at_id})的等级提升为{get_level(at_id, group_id)}级,积分清零喵。",
                    )

                elif HasKeyWords(raw_message, ["惩罚取消", "取消惩罚"]) and (
                    (user_id != at_id and IsAdmin(user_id, group_id))
                    or IsDeveloper(user_id)
                ):
                    DelAtPunish(at_id, group_id)
                    logging.info(
                        f"{group_id}:{sender_name}({user_id})取消了{rev_name}({at_id})的惩罚"
                    )
                    await SayGroup(
                        websocket,
                        group_id,
                        f"{rev_name}({at_id})的惩罚被{sender_name}({user_id})取消了,快谢谢人家喵！",
                    )
                    await ban_new(websocket, at_id, group_id, 0)

                elif HasKeyWords(raw_message, ["送你", "V你", "v你"]):
                    num = re.findall(r"\d+", raw_message)
                    if len(num) >= 2:
                        num = int(num[1])
                    else:
                        num = 0
                    await GiveGift(websocket, user_id, group_id, at_id, num)

                elif HasKeyWords(raw_message, ["你是GAY", "你是gay"]) and IsAdmin(
                    user_id, group_id
                ):
                    # todo 修复bug
                    # if at_id not in load_setting["boring"]:
                    #     _setting = load_setting()
                    #     _setting["boring"].append(at_id)
                    #     dump_setting(_setting)
                    # await say(
                    #     websocket,
                    #     group_id,
                    #     f"{get_user_name(at_id, group_id)},GAY追杀令喵!!!!",
                    # )
                    pass
                elif HasKeyWords(raw_message, ["你不是GAY", "你不是gay"]) and IsAdmin(
                    user_id, group_id
                ):
                    _setting = load_setting("boring", [])
                    while at_id in _setting:
                        _setting.remove(at_id)
                    dump_setting("boring", _setting)
                    await SayGroup(
                        websocket,
                        group_id,
                        f"{get_user_name(at_id, group_id)},GAY追杀令取消了喵。",
                    )
                elif HasKeyWords(raw_message, ["不要哈气"]) and IsAdmin(
                    user_id, group_id
                ):
                    _setting = load_setting("huffing", [])
                    while at_id in _setting:
                        _setting.remove(at_id)
                    dump_setting("huffing", _setting)
                    await SayGroup(
                        websocket,
                        group_id,
                        f"{get_user_name(at_id, group_id)},乐可停止追杀你了喵！",
                    )
                elif HasKeyWords(raw_message, ["哈气"]) and IsAdmin(user_id, group_id):
                    _setting = load_setting("huffing", [])
                    if at_id not in _setting:
                        _setting.append(at_id)
                        dump_setting("huffing", _setting)
                    await SayGroup(
                        websocket,
                        group_id,
                        f"{get_user_name(at_id, group_id)},乐可要追杀你了喵！",
                    )
                elif HasKeyWords(
                    raw_message,
                    [
                        "不要装",
                    ],
                ) and IsAdmin(user_id, group_id):
                    _setting = load_setting("fly", [])
                    if at_id not in _setting:
                        _setting.append(at_id)
                        dump_setting("fly", _setting)
                    await SayGroup(
                        websocket,
                        group_id,
                        f"{get_user_name(at_id, group_id)},不要再装了喵。",
                    )
                elif HasKeyWords(
                    raw_message,
                    [
                        "可以装",
                    ],
                ) and IsAdmin(user_id, group_id):
                    _setting = load_setting("fly", [])
                    while at_id in _setting:
                        _setting.remove(at_id)
                    dump_setting("fly", _setting)
                    await SayGroup(
                        websocket,
                        group_id,
                        f"{get_user_name(at_id, group_id)},可以开始装了喵。",
                    )
                elif (
                    HasKeyWords(raw_message, ["打他", "打它", "打她"])
                    and (user_id != at_id or IsDeveloper(user_id))
                    and IsAdmin(user_id, group_id)
                ):
                    AddAtPunishList(
                        at_id,
                        group_id,
                        load_setting("defense_times", 100),
                    )
                    await SayGroup(
                        websocket,
                        group_id,
                        f"{get_user_name(user_id, group_id)},乐可要开始打你了喵！",
                    )

                elif HasKeyWords(raw_message, ["通过验证", "验证通过"]):
                    from application.welcome_application import (
                        find_vcode,
                        verify,
                        welcome_new,
                        welcom_new_no_admin,
                    )

                    (mod, vcode_str) = find_vcode(at_id, group_id)
                    if mod:
                        (mod, times) = verify(
                            at_id,
                            group_id,
                            vcode_str,
                        )
                        if mod:
                            # 通过验证
                            if BotIsAdmin(group_id):
                                if group_id == load_setting("admin_group_main", 0):
                                    await ban_new(
                                        websocket,
                                        at_id,
                                        group_id,
                                        60,
                                    )
                                    await welcome_new(websocket, at_id, group_id)
                                else:
                                    await welcom_new_no_admin(
                                        websocket, at_id, group_id
                                    )
                            else:
                                await welcom_new_no_admin(websocket, at_id, group_id)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return True


from tools.tools import timestamp_to_date
from function.say import SayGroupReturnMessageId

# 丢漂流瓶


async def throw_drifting_bottles(websocket, user_id: int, group_id: int, text: str):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    uid = str(uuid.uuid4())
    try:
        cur.execute(
            "INSERT INTO drifting_bottles (uuid,user_id,group_id,text,pick_times,time)VALUES (?,?,?,?,?,?);",
            (uid, user_id, group_id, text, 0, time.time()),
        )
        conn.commit()
    except sqlite3.OperationalError:
        logging.info("数据库表不存在,正在创建表drifting_bottles")
        cur.execute(
            "CREATE TABLE drifting_bottles (uuid TEXT, user_id INTEGER, group_id INTEGER, text TEXT, pick_times INTEGER, time INTEGER); "
        )
        conn.commit()
        cur.execute(
            "INSERT INTO drifting_bottles (uuid,user_id,group_id,text,pick_times,time)VALUES (?,?,?,?,?,?);",
            (uid, user_id, group_id, text, 0, time.time()),
        )
        conn.commit()
    conn.close()
    # await say(
    #     websocket,
    #     group_id,
    #     f"{get_user_name(user_id,group_id)},成功丢出了一个漂流瓶,标识ID为:{uid}",
    # )
    await SayGroup(
        websocket,
        group_id,
        f"{get_user_name(user_id,group_id)},成功丢出了一个漂流瓶,等待有缘人捞起喵。",
    )
    return uid


# 随机捞漂流瓶
async def pick_drifting_bottles_radom(websocket, user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM drifting_bottles ORDER BY RANDOM() LIMIT 1;")
    except sqlite3.OperationalError:
        logging.info("数据库表不存在,正在创建表drifting_bottles")
        cur.execute(
            "CREATE TABLE drifting_bottles ( uuid   TEXT, user_id    INTEGER, group_id   INTEGER, text   TEXT, pick_times INTEGER, time  INTEGER ); "
        )
        conn.commit()
        await SayGroup(
            websocket,
            group_id,
            f"{get_user_name(user_id,group_id)},没有漂流瓶了喵，待会再来吧喵。",
        )
        return
    row = cur.fetchone()
    if row is None:
        await SayGroup(
            websocket,
            group_id,
            f"{get_user_name(user_id,group_id)},没有漂流瓶了喵，待会再来吧喵。",
        )
        return
    else:
        text = f"捞到了一个{get_user_name(row[1],row[2])}于{timestamp_to_date(row[5])}在{GetGroupName(row[2])}丢的漂流瓶。\n{row[3]}"
        # user_id, group_id, text, time
        all_comment = load_comment(row[0])
        for comment in all_comment:
            text = (
                text
                + f"\n{timestamp_to_date(comment[3])}({GetGroupName(comment[1])}){get_user_name(comment[0],comment[1])}:{comment[2]}"
            )
        messageId = SayGroupReturnMessageId(group_id, text)
        write_bottles_uuid_message_id(messageId, row[0], group_id)
        cur.execute(
            "UPDATE drifting_bottles SET pick_times = pick_times + 1 WHERE uuid = ?;",
            (row[0],),
        )
        conn.commit()
        return messageId


# 写入评论
def dump_comment(uuid: str, user_id: int, group_id: int, text: str):
    matches = re.search(r"\[(.*?)\]\[(.*?)\]\s*(.*)", text)
    if matches:
        text = matches.group(3)
    else:
        matches = re.search(r"\[(.*?)\]\s*(.*)", text)
        if matches:
            text = matches.group(2)
        else:
            return
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO drifting_bottles_comments (user_id,group_id,text,time,uuid)VALUES (?,?,?,?,?);",
            (user_id, group_id, text, time.time(), uuid),
        )
        conn.commit()
    except sqlite3.OperationalError:
        logging.info("数据库表不存在,正在创建表drifting_bottles_comments")
        cur.execute(
            "CREATE TABLE drifting_bottles_comments(user_id INTEGER, group_id INTEGER, text TEXT, time INTEGER,uuid TEXT); "
        )
        conn.commit()
        cur.execute(
            "INSERT INTO drifting_bottles_comments (user_id,group_id,text,time)VALUES (?,?,?,?,?);",
            (user_id, group_id, text, time.time(), uuid),
        )
        conn.commit()
    conn.close()


# 读取评论
def load_comment(uuid: str):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT user_id, group_id, text, time FROM drifting_bottles_comments where uuid = ?; ",
            (uuid,),
        )
    except sqlite3.OperationalError:
        logging.info("数据库表不存在,正在创建表drifting_bottles_comments")
        cur.execute(
            "CREATE TABLE drifting_bottles_comments(user_id INTEGER, group_id INTEGER, text TEXT, time INTEGER,uuid TEXT); "
        )
        conn.commit()
        cur.execute(
            "SELECT user_id, group_id, text, time FROM drifting_bottles_comments where uuid = ?; ",
            (uuid,),
        )
    all = cur.fetchall()
    conn.close()
    if len(all) == 0:
        return []
    else:
        return all


# 漂流瓶消息ID写入数据库，方便评论
def write_bottles_uuid_message_id(message_id: int, uuid: str, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO bottles_uuid_message_id (message_id,uuid,group_id)VALUES (?,?,?);",
            (message_id, uuid, group_id),
        )
        conn.commit()
    except sqlite3.OperationalError:
        logging.info("数据库表不存在,正在创建表bottles_uuid_message_id")
        cur.execute(
            "CREATE TABLE bottles_uuid_message_id ( message_id   INTEGER, uuid   TEXT, group_id   INTEGER ); "
        )
        conn.commit()
        cur.execute(
            "INSERT INTO bottles_uuid_message_id (message_id,uuid,group_id)VALUES (?,?,?);",
            (message_id, uuid, group_id),
        )
        conn.commit()
    conn.close()


def IsComment(user_id: int, group_id: int, reply_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT uuid FROM bottles_uuid_message_id where message_id=? and group_id=?",
            (reply_id, group_id),
        )
    except sqlite3.OperationalError:
        logging.info("数据库表不存在,正在创建表bottles_uuid_message_id")
        cur.execute(
            "CREATE TABLE bottles_uuid_message_id ( message_id   INTEGER, uuid   TEXT, group_id   INTEGER ); "
        )
        conn.commit()
        cur.execute(
            "SELECT uuid FROM bottles_uuid_message_id where message_id=? and group_id=?",
            (reply_id, group_id),
        )
    a = cur.fetchone()
    if a == None:
        return False
    else:
        if len(a) > 0:
            return True
    return False


async def WriteBottlesComment(
    websocket, userId: int, groupId: int, plainMessage: str, replyId: int
):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT uuid FROM bottles_uuid_message_id where message_id=? and group_id=?",
            (replyId, groupId),
        )
    except sqlite3.OperationalError:
        logging.info("数据库表不存在,正在创建表bottles_uuid_message_id")
        cur.execute(
            "CREATE TABLE bottles_uuid_message_id ( message_id   INTEGER, uuid   TEXT, group_id   INTEGER ); "
        )
        conn.commit()
        cur.execute(
            "SELECT uuid FROM bottles_uuid_message_id where message_id=? and group_id=?",
            (replyId, groupId),
        )
    uuid = cur.fetchone()
    dump_comment(uuid, userId, groupId, plainMessage)
    return uuid


# 判断是否为评论并写入
async def is_comment_write(websocket, user_id: int, group_id: int, raw_message: str):
    match = re.search(r"\[CQ:reply,id=(\d+)\]", raw_message)
    if match:
        message_id = int(match.group(1))
        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT uuid FROM bottles_uuid_message_id where message_id=? and group_id=?",
                (message_id, group_id),
            )
        except sqlite3.OperationalError:
            logging.info("数据库表不存在,正在创建表bottles_uuid_message_id")
            cur.execute(
                "CREATE TABLE bottles_uuid_message_id ( message_id   INTEGER, uuid   TEXT, group_id   INTEGER ); "
            )
            conn.commit()
            cur.execute(
                "SELECT uuid FROM bottles_uuid_message_id where message_id=? and group_id=?",
                (message_id, group_id),
            )
        a = cur.fetchone()
        if a == None:
            return False
        else:
            if len(a) > 0:
                uuid = a[0]
                if not HasKeyWords(raw_message, ["[CQ:image"]):
                    dump_comment(uuid, user_id, group_id, raw_message)
                    await ReplySay(
                        websocket,
                        group_id,
                        message_id,
                        f"评论ID为{uuid}的漂流瓶成功喵!",
                    )
                    return True
                else:
                    return False
    else:
        return False


class DriftBottleApplication(GroupMessageApplication):
    """漂流瓶应用"""

    def __init__(self):
        applicationInfo = ApplicationInfo("漂流瓶应用", "可以捞和捡漂流瓶")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        websocket = message.websocket
        group_id = message.groupId
        user_id = message.senderId
        message_id = message.messageId
        if HasKeyWords(
            message.plainTextMessage,
            [
                "捡漂流瓶",
                "捞漂流瓶",
            ],
        ):
            await pick_drifting_bottles_radom(websocket, user_id, group_id)
        else:
            # 丢漂流瓶
            if len(message.imageFileList) != 0:
                await SayGroup(
                    websocket,
                    group_id,
                    f"{get_user_name(user_id, group_id)},暂时不支持图片喵。",
                )
            else:
                match = re.search(
                    r"throw\s*([\s\S]*)$",
                    message.plainTextMessage,
                )
                if match:
                    print(match.group(1))
                    uid = await throw_drifting_bottles(
                        websocket,
                        user_id,
                        group_id,
                        match.group(1),
                    )
                    write_bottles_uuid_message_id(message_id, uid, group_id)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage,
            ["throw", "丢漂流瓶"],
        ) or HasKeyWords(
            message.plainTextMessage,
            [
                "捡漂流瓶",
                "捞漂流瓶",
            ],
        )


class CommentDriftBottleApplication(GroupMessageApplication):
    """评论漂流瓶应用"""

    def __init__(self):
        applicationInfo = ApplicationInfo("评论漂流瓶应用", "可以评论漂流瓶")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        websocket = message.websocket
        groupId = message.groupId
        messageId = message.messageId
        uuid = await WriteBottlesComment(
            websocket,
            message.senderId,
            groupId,
            message.plainTextMessage,
            message.replyMessageId,
        )
        await ReplySay(
            websocket,
            groupId,
            messageId,
            f"评论ID为{uuid}的漂流瓶成功喵!",
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return (
            IsComment(message.senderId, message.groupId, message.messageId)
            and message.replyMessageId != -1
        )


from function.group_operation import GetGroupMessageSenderId

# 特殊回复应用
class SpicalReplyApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("特殊回复应用", "特殊回复应用", False)
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        sender_id = GetGroupMessageSenderId(message.replyMessageId)
        now_point = find_point(sender_id)
        if message.plainTextMessage.startswith("好好好"):
            change_point(sender_id, message.groupId, now_point + 100)
            sender_name = get_user_name(sender_id, message.groupId)
            await ReplySay(
                message.websocket,
                message.groupId,
                message.replyMessageId,
                "{},受到☁️赞扬,积分:{}->{}".format(
                    sender_name, now_point, now_point + 100
                ),
            )
        elif message.plainTextMessage.startswith("坏坏坏"):
            change_point(sender_id, message.groupId, now_point - 100)
            sender_name = get_user_name(sender_id, message.groupId)
            await ReplySay(
                message.websocket,
                message.groupId,
                message.replyMessageId,
                "{},不要搬💩了喵,积分:{}->{}".format(
                    sender_name, now_point, now_point - 100
                ),
            )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return (
            (
                message.plainTextMessage.startswith("好好好")
                or message.plainTextMessage.startswith("坏坏坏")
            )
            and message.senderId in load_setting("developers_list", [])
            and message.replyMessageId != -1
        )


from function.group_operation import SetEssenceMsg, DeleteEssenceMsg

# 加精/移除加精应用
class EssenceAboutGroupMessageApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo(
            "加精/移除加精应用",
            f"引用回复消息,说{load_setting("bot_name","乐可")},加精/移除加精",
        )
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息

        if message.plainTextMessage.startswith("加精"):
            await SetEssenceMsg(message.websocket, message.replyMessageId)

        elif message.plainTextMessage.startswith("移除加精"):
            await DeleteEssenceMsg(message.websocket, message.replyMessageId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return (
            (
                message.plainTextMessage.startswith("加精")
                or message.plainTextMessage.startswith("移除加精")
            )
            and BotIsAdmin(message.groupId)
            and message.replyMessageId != -1
        )


# 你们看到她了吗
async def SoCute(websocket, user_id: int, group_id: int):
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {
                    "type": "image",
                    "data": {
                        "file": f"https://api.tangdouz.com/wz/cute.php?q={user_id}"
                    },
                },
            ],
        },
    }
    await websocket.send(json.dumps(payload))


class WhoLookYouApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo(
            "你们看到他了嘛?",
            f"引用回复消息,说你们看到他了嘛?",
        )
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息

        group_id = message.groupId
        sender_id = GetGroupMessageSenderId(message.replyMessageId)
        await SoCute(message.websocket, sender_id, group_id)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return (
            HasAllKeyWords(message.plainTextMessage, ["看到", "了", "你"])
            and HasKeyWords(message.plainTextMessage, ["吗", "嘛"])
            and message.replyMessageId != -1
        )


from tools.tools import HasChinese

# 香香软软小南梁群友功能
class GroupKotomitakoApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo(
            "香香软软小南梁群友",
            f"香香软软小南梁群友,说话要带第一人称代词要用咱得带喵。",
        )
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        if "喵" not in message.plainTextMessage:
            await ban_new(
                message.websocket,
                message.senderId,
                message.groupId,
                60,
            )
            if "我" in message.plainTextMessage:
                await ReplySay(
                    message.websocket,
                    message.groupId,
                    message.messageId,
                    f"{get_user_name(message.senderId, message.groupId)},你作为本群的香香软软小南梁，因为不用咱自称被禁言了喵。",
                )
            else:
                await ReplySay(
                    message.websocket,
                    message.groupId,
                    message.messageId,
                    f"{get_user_name(message.senderId, message.groupId)},你作为本群的香香软软小南梁，因为不带喵被禁言了喵。",
                )
        elif "我" in message.plainTextMessage:
            await ReplySay(
                message.websocket,
                message.groupId,
                message.messageId,
                f"{get_user_name(message.senderId, message.groupId)},你作为本群的香香软软小南梁，因为不用咱自称被禁言了喵。",
            )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return message.senderId in get_config("kotomitako", message.groupId) and BotIsAdmin(message.groupId) and HasChinese(message.plainTextMessage)  # type: ignore

# 猫娘群友
class GroupMiaoMiaoApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo(
            "猫娘群友",
            "猫娘群友,说话得带喵。",
        )
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await ban_new(
            message.websocket,
            message.senderId,
            message.groupId,
            60,
        )
        await ReplySay(
            message.websocket,
            message.groupId,
            message.messageId,
            "{},你因为说话不带喵被禁言了喵。".format(
                get_user_name(message.senderId, message.groupId)
            ),
        )
        await ban_new(
            message.websocket,
            message.senderId,
            message.groupId,
            0,
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return message.senderId in get_config("catgirl", message.groupId) and BotIsAdmin(message.groupId) and HasChinese(message.plainTextMessage) and "喵" not in message.plainTextMessage  # type: ignore


from datetime import datetime

# 喵喵日
class GroupMiaoMiaoDayApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo(
            "喵喵日",
            "喵喵日，那天所以人说话都要带喵。",
        )
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        if IsAdmin(message.senderId, message.groupId) and not get_config(
            "cat_day_ignore_admin", message.groupId
        ):
            await ReplySay(
                message.websocket,
                message.groupId,
                message.messageId,
                f"{get_user_name(message.senderId, message.groupId)},每月{get_config("cat_day_date", message.groupId)}号是本群喵喵日,虽然你是管理,{load_setting("bot_name","乐可")}禁言不了你喵，但是希望你还是喵一下子喵。",
            )
        else:
            await ban_new(
                message.websocket,
                message.senderId,
                message.groupId,
                60,
            )
            await ReplySay(
                message.websocket,
                message.groupId,
                message.messageId,
                "{},每月{}号是本群喵喵日,你因为说话不带喵被禁言了喵。".format(
                    get_user_name(message.senderId, message.groupId),
                    get_config("cat_day_date", message.groupId),
                ),
            )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return (
            "喵" not in message.plainTextMessage
            and len(message.imageFileList) == 0
            and len(message.imageFileList) == 0
            and HasChinese(message.plainTextMessage)
            and datetime.now().day == get_config("cat_day_date", message.groupId)
            and BotIsAdmin(message.groupId)
        )
