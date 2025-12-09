import base64
from datetime import datetime
import glob
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
        super().__init__(applicationInfo, 65, False, ApplicationCostType.NORMAL)

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

from tools.tools import GetNCWCPort, GetNCHSPort, GetOllamaPort


# 发送获取群名单
def get_group_list(websocket):
    url = f"http://localhost:{GetNCHSPort()}/get_group_list"
    resp = requests.post(url)
    data = resp.json()
    return data["data"]


# 发送更新群成员名单
def update_group_member_list(websocket, group_id: int):
    import json

    url = f"http://localhost:{GetNCHSPort()}/get_group_member_list"
    payload = {"group_id": group_id}
    resp = requests.post(url, json=payload)
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
    """
    定时刷新群成员数据库应用类
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
            _setting = load_setting("group_list", [])
            dump_setting("last_update_time", time.time())
            data = get_group_list(message.websocket)
            print("开始更新群列表")
            # logging.info("开始更新群列表")
            for group in data:
                update_group_info(
                    group["group_id"],
                    group["group_name"],
                    group["member_count"],
                    group["max_member_count"],
                )
                if group["group_id"] not in _setting:
                    _setting.append(group["group_id"])
                    dump_setting("group_list", _setting)
                new_data = update_group_member_list(
                    message.websocket, group["group_id"]
                )
                if new_data is None:
                    logging.error(
                        f"更新群成员列表失败,群:{group['group_name']}({group['group_id']})"
                    )
                    continue
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
                            if user.user_id != 0 and not IsAdmin(
                                user.user_id, user.group_id
                            ):
                                print(
                                    "{}({})因{}个月未活跃被请出群聊{}({}),最后发言时间:{}".format(
                                        name,
                                        user.user_id,
                                        round(timeout / 2592000, 2),  # type: ignore
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
                                        round(timeout / 2592000, 2),  # type: ignore
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
                                        round(timeout / 2592000, 2),  # type: ignore
                                        time.strftime(
                                            "%Y-%m-%d %H:%M:%S",
                                            time.localtime(user.last_sent_time),
                                        ),
                                    ),
                                )
                                await kick_member(
                                    message.websocket, user.user_id, user.group_id
                                )
                # logging.info(f'更新群:{group["group_name"]}({group["group_id"]})完成。')

            print("更新全部群列表完毕")
            # logging.info("更新全部群列表完毕")

    def judge(self, message: MetaMessageInfo) -> bool:
        """判断是否触发应用"""
        return (
            message.metaEventType == MetaEventType.HEART_BEAT
            and time.time() - load_setting("last_update_time", 0) > 300
        )


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


# 无聊功能合集
# 哈气，装，打，GAY [AT管理]
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
                f'艾特惩罚,剩余:{admin["num"]-1}次喵.',
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
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

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
                if at_id in load_setting("boring", []):
                    _setting.remove(at_id)
                dump_setting("boring", _setting)
                await SayGroup(
                    websocket,
                    group_id,
                    f"{get_user_name(at_id, group_id)},GAY追杀令取消了喵。",
                )
            elif HasKeyWords(raw_message, ["不要哈气"]) and IsAdmin(user_id, group_id):
                _setting = load_setting("huffing", [])
                if at_id in load_setting("huffing", []):
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
        return len(message.atList) != 0 and HasKeyWords(
            message.plainTextMessage,
            [
                "你是GAY",
                "你是gay",
                "你不是GAY",
                "你不是gay",
                "不要哈气",
                "哈气",
                "不要装",
                "可以装",
                "打他",
                "打它",
                "打她",
            ],
        )


class BoringFeatureCollectionApplication(GroupMessageApplication):
    """无聊功能触发合集(除艾特惩罚)"""

    def __init__(self):
        applicationInfo = ApplicationInfo("无聊功能触发合集", "无聊功能触发合集")
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
        return (
            message.senderId in load_setting("boring", [])
            or message.senderId in load_setting("huffing", [])
            or message.senderId in load_setting("fly", [])
        )


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
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

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


# 艾特功能大合集
from application.welcome_application import (
    find_vcode,
    verify,
    welcome_new,
    welcom_new_no_admin,
)


class AtManagementApplication(GroupMessageApplication):
    """艾特功能大合集"""

    def __init__(self):
        applicationInfo = ApplicationInfo("艾特功能大合集", "提供一些艾特功能")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        # 处理消息
        user_id = message.senderId
        group_id = message.groupId
        websocket = message.websocket
        raw_message = message.plainTextMessage
        for at_id in message.atList:
            rev_name = get_user_name(at_id, group_id)
            sender_name = get_user_name(user_id, group_id)
            if (
                "解除禁言" in raw_message
                and BotIsAdmin(group_id)
                and IsAdmin(user_id, group_id)
            ):
                logging.info(
                    f"{group_id}:{sender_name}({user_id})解除禁言了{rev_name}({at_id})"
                )
                await ban_new(websocket, at_id, group_id, 0)

            elif (
                "禁言" in raw_message
                and BotIsAdmin(group_id)
                and IsAdmin(user_id, group_id)
            ):
                logging.info(
                    f"{group_id}:{sender_name}({user_id})禁言了{rev_name}({at_id})"
                )
                await ban_new(websocket, at_id, group_id, 1800)

            elif (
                "说再见" in raw_message
                and BotIsAdmin(group_id)
                and IsAdmin(user_id, group_id)
            ):
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
                if len(num) > 0:
                    num = int(num[0])
                else:
                    num = 0

                await GiveGift(websocket, user_id, group_id, at_id, num)

            elif HasKeyWords(raw_message, ["你是GAY", "你是gay"]) and IsAdmin(
                user_id, group_id
            ):
                _setting = load_setting("boring", [])
                if at_id not in _setting:
                    _setting.append(at_id)
                    dump_setting("boring", _setting)
                await SayGroup(
                    websocket,
                    group_id,
                    f"{get_user_name(at_id, group_id)},GAY追杀令喵!!!!",
                )
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
            elif HasKeyWords(raw_message, ["不要哈气"]) and IsAdmin(user_id, group_id):
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

            elif (
                HasKeyWords(raw_message, ["通过验证", "验证通过"])
                and BotIsAdmin(group_id)
                and IsAdmin(user_id, group_id)
            ):
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
                                await welcom_new_no_admin(websocket, at_id, group_id)
                        else:
                            await welcom_new_no_admin(websocket, at_id, group_id)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return len(message.atList) > 0 and HasKeyWords(
            message.plainTextMessage,
            [
                "解除禁言",
                "禁言",
                "说再见",
                "晋升",
                "惩罚取消",
                "取消惩罚",
                "送你",
                "V你",
                "v你",
                "你是GAY",
                "你是gay",
                "你不是GAY",
                "你不是gay",
                "不要哈气",
                "哈气",
                "不要装",
                "可以装",
                "打他",
                "打它",
                "打她",
                "通过验证",
                "验证通过",
            ],
        )


# 赠送积分应用


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
    uuid = uuid[0]
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
            IsComment(message.senderId, message.groupId, message.replyMessageId)
            and message.replyMessageId != -1
        )


from function.group_operation import GetGroupMessageSenderId


# 返回text里面有多少个好字
def findGoodNums(text: str) -> int:
    return text.count("好")


# 返回text里面有多少个坏字
def findBadNums(text: str) -> int:
    return text.count("坏")


# 特殊回复应用
class SpicalReplyApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("特殊回复应用", "特殊回复应用", False)
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        sender_id = GetGroupMessageSenderId(message.replyMessageId)
        now_point = find_point(sender_id)
        if message.plainTextMessage.startswith("好好好"):
            good_nums = findGoodNums(message.plainTextMessage)
            if good_nums <= 3:
                changed_point = 100
            else:
                changed_point = 100 * good_nums
            change_point(sender_id, message.groupId, now_point + changed_point)
            sender_name = get_user_name(sender_id, message.groupId)
            await ReplySay(
                message.websocket,
                message.groupId,
                message.replyMessageId,
                "{},受到☁️赞扬,积分:{}->{}".format(
                    sender_name, now_point, now_point + changed_point
                ),
            )
        elif message.plainTextMessage.startswith("坏坏坏"):
            bad_nums = findBadNums(message.plainTextMessage)
            if bad_nums <= 3:
                changed_point = 100
            else:
                changed_point = 100 * bad_nums
            change_point(sender_id, message.groupId, now_point - changed_point)
            sender_name = get_user_name(sender_id, message.groupId)
            await ReplySay(
                message.websocket,
                message.groupId,
                message.replyMessageId,
                "{},不要搬💩了喵,积分:{}->{}".format(
                    sender_name, now_point, now_point - changed_point
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
            f'引用回复消息,说{load_setting("bot_name","乐可")},加精/移除加精',
        )
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

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
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

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
        return message.senderId in get_config("kotomitako", message.groupId) and BotIsAdmin(message.groupId) and HasChinese(message.plainTextMessage) and len(message.atList) == 0 and message.replyMessageId == -1  # type: ignore


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
        return message.senderId in get_config("catgirl", message.groupId) and BotIsAdmin(message.groupId) and HasChinese(message.plainTextMessage) and "喵" not in message.plainTextMessage and len(message.imageFileList) == 0 and len(message.atList) == 0 and message.replyMessageId == -1 and len(message.plainTextMessage) < 50  # type: ignore


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
            botName = load_setting("bot_name", "乐可")
            maoDay = get_config("cat_day_date", message.groupId)
            userName = get_user_name(message.senderId, message.groupId)
            await ReplySay(
                message.websocket,
                message.groupId,
                message.messageId,
                f"{userName},每月{maoDay}号是本群喵喵日,虽然你是管理,{botName}禁言不了你喵，但是希望你还是喵一下子喵。",
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
            and len(message.atList) == 0
            and message.replyMessageId == -1
            and HasChinese(message.plainTextMessage)
            and datetime.now().day == get_config("cat_day_date", message.groupId)
            and BotIsAdmin(message.groupId)
        )


# 乐可不是可乐


# 不要叫乐可可乐
async def cute2(websocket, group_id: int):
    path = "res/cute2.gif"
    logging.info("有人叫乐可可乐。")
    with open(path, "rb") as image_file:
        image_data = image_file.read()
    image_base64 = base64.b64encode(image_data)
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {
                    "type": "text",
                    "data": {
                        "text": "抗议！！！抗议！！！人家叫乐可喵，不叫可乐喵！！！！",
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


class LeKeNotKeleApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("乐可不是可乐", "乐可不是可乐", False)
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await cute2(message.websocket, message.groupId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return message.plainTextMessage.startswith("可乐")


from function.say import SayImgReply


# 早安应用
class GoodMorningApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("早安应用", "早安应用", False)
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await SayImgReply(
            message.websocket,
            message.senderId,
            message.groupId,
            message.messageId,
            "早上好喵！",
            "res/good_morning.jpg",
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return (
            HasKeyWords(
                message.plainTextMessage,
                ["早安", "早上好", "早"],
            )
            and datetime.now().hour < 10
            and datetime.now().hour >= 6
        )


# 功能菜单应用


async def return_function(websocket, user_id: int, group_id: int):
    with open("res/function.png", "rb") as image_file:
        image_data = image_file.read()
    image_base64 = base64.b64encode(image_data)
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {
                    "type": "text",
                    "data": {
                        "text": """
    "catgirl": [],  # 猫娘群友
    "kotomitako": [],  # 香香软软小南梁群友
    "blacklist": [],  # 黑名单群友
    "no_reply_list": [],  # 不回复的群友
    "cold_group": False,  # 冷群回复开关
    "cold_group_num_out": 5,  # 多少句触发冷群
    "cold_group_time_out": 300,  # 多久触发冷群
    "group_decrease_reminder": True,  # 退群提醒
    "cat_day_date": -1,  # 猫猫日日期，-1表示不设置
    "cat_day_ignore_admin": True,  # 猫猫日忽略管理员
    "kick_time_sec": -1,  # 踢掉多久没发言的群友，-1表示不踢
"""
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


class FeaturesMenuApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("功能菜单", "功能菜单", False)
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await return_function(message.websocket, message.senderId, message.groupId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [f"{load_setting("bot_name", "乐可")},功能"]  # type: ignore
        )


# 每日一言
async def daily_word(websocket, user_id: int, group_id: int):
    r = requests.get("https://api.tangdouz.com/a/perday.php", timeout=60)
    # print(r.text)
    text = r.text.split("±")
    # print(text)
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {"type": "image", "data": {"file": text[1][4:]}},
                {
                    "type": "text",
                    "data": {
                        "text": "{}\n{}".format(
                            text[2].split("\\r")[0], text[2].split("\\r")[1]
                        )
                    },
                },
            ],
        },
    }
    # print(payload)
    await websocket.send(json.dumps(payload))


class EveryDayOnePassageApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("每日一言", "每日一言")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await daily_word(message.websocket, message.senderId, message.groupId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage,
            ["每日一句"],
        ) and HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]  # type: ignore
        )


# 黑名单查询
class BlacklistQueryApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("黑名单查询", "黑名单查询")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        user_id = re.search(
            r"\d+",
            message.plainTextMessage,
        ).group()  # type: ignore
        if user_id in list(load_setting("blacklist", {}).keys()):
            await SayGroup(
                message.websocket,
                message.groupId,
                "{}在黑名单中，原因:{}。".format(
                    user_id,
                    load_setting("blacklist", {}).get(user_id),
                ),
            )

        else:
            await SayGroup(
                message.websocket,
                message.groupId,
                "{}不在黑名单中".format(user_id),
            )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage,
            ["查询黑名单"],
        ) and HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]  # type: ignore
        )


# 今天吃什么
class TodayEatWhatApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("今天吃什么", "今天吃什么")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await ban_new(
            message.websocket,
            message.senderId,
            message.groupId,
            60,
        )
        await SayAndAt(
            message.websocket,
            message.senderId,
            message.groupId,
            ",吃大嘴巴子🖐喵。",
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage,
            ["吃什么"],
        ) and HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]  # type: ignore
        )


# 群友的恶趣味功能
async def WhoAskPants(websocket, group_id: int):
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [],
        },
    }
    payload["params"]["message"].append(
        {
            "type": "text",
            "data": {"text": "你问的胖次我不知道喵,但是我知道群友最喜欢的胖次。"},
        }
    )
    file_dir = "res/1.jpg"
    # print(file_dir)
    with open(file_dir, "rb") as image_file:
        image_data = image_file.read()
    image_base64 = base64.b64encode(image_data)
    payload["params"]["message"].append(
        {
            "type": "image",
            "data": {"file": "base64://" + image_base64.decode("utf-8")},
        }
    )
    await websocket.send(json.dumps(payload))


class GroupFriendBadTasteApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("群友的恶趣味", "群友的恶趣味", False)
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await WhoAskPants(message.websocket, message.groupId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage,
            ["胖次", "内裤"],
        ) and HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]  # type: ignore
        )


# 大头菜
# B股股指
import tushare as ts


def GetBShock():
    ts.set_token(load_setting("tushare_token", ""))
    df = ts.realtime_quote(ts_code="000003.SH")
    return df.PRICE[0]  # type: ignore


def GetDogeCoinV2():
    import re
    from requests_html import HTMLSession

    try:
        s = HTMLSession()
        response = s.get("https://www.528btc.com/coin/2993/binance-doge-usdt-usd")
        # print(response.text)
        # with open("tmp.html", "w", encoding="utf-8") as f:
        #     f.write(response.text)
        pattern = re.compile(
            '<i class="price_num wordRise">(.*?)</i>',
        )
        m = pattern.findall(response.text)
        if len(m) != 0:
            setting = float(m[0])
            dump_setting("kohlrabi_price", setting)
            return m[0]
        else:
            pattern = re.compile(
                '<i class="price_num wordFall">(.*?)</i>',
            )
            m = pattern.findall(response.text)
            setting = float(m[0])
            dump_setting("kohlrabi_price", setting)
            return m[0]
    except:
        setting = load_setting("kohlrabi_price", 100)
        print("获取大头菜价格失败，使用上一次的价格:{}".format(setting))
        logging.info("获取大头菜价格失败，使用上一次的价格:{}".format(setting))
        return setting


# 狗狗币
def GetDogeCoin():
    import re
    import requests

    try:
        r = requests.get("https://bitcompare.net/zh-cn/coins/dogecoin", timeout=60)
        # with open("tmp.txt", "w", encoding="utf-8") as f:
        #     f.write(r.text)
        pattern = re.compile(
            'placeholder="0.00" min="0" step="1" value="(.*?)"/>',
        )
        m = pattern.findall(r.text)
        setting = load_setting("kohlrabi_price", 100)
        setting = float(m[0])
        dump_setting("kohlrabi_price", setting)
        return m[0]
    except:
        setting = load_setting("kohlrabi_price", 100)
        logging.info("获取大头菜价格失败，使用上一次的价格:{}".format(setting))
        return setting


# 获取大头菜价格
def GetNowPrice():
    setting = load_setting("kohlrabi_version", 0)
    if setting == 0:
        now_price = GetBShock()
        now_price = round(float(now_price), 3)
    elif setting == 1:
        now_price = GetDogeCoin()
        now_price = round(float(now_price) * 1000, 3)
    else:
        now_price = GetDogeCoinV2()
        now_price = round(float(now_price) * 1000, 3)
    return now_price


# 获取我的本周交易记录
def GetMyKohlrabi(user_id: int, group_id: int):
    now_week = time.strftime("%W")
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT nums FROM kohlrabi_week where user_id=? and group_id=?;",
        (
            user_id,
            group_id,
        ),
    )
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO kohlrabi_week (user_id,group_id,nums,now_weeks)VALUES (?,?,0,?);",
            (
                user_id,
                group_id,
                now_week,
            ),
        )
        conn.commit()
        conn.close()
        return 0
    else:
        conn.close()
        return data[0][0]


# 定期清理过期对的大头菜
def ClearKohlrabi():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM kohlrabi_week WHERE  now_weeks != ?;", (time.strftime("%W"),)
    )
    conn.commit()
    conn.close()


# 改变大头菜本周交易记录
def ChangeMyKohlrabi(user_id: int, group_id: int, nums: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE kohlrabi_week SET nums = ? WHERE user_id = ? AND group_id = ?;",
        (nums, user_id, group_id),
    )
    conn.commit()
    conn.close()


# 梭哈
async def ShowHand(websocket, user_id: int, group_id: int):
    import math

    now_num = GetMyKohlrabi(user_id, group_id)
    now_point = find_point(user_id)
    now_price = GetNowPrice()
    if now_point > now_price:
        num = math.trunc(now_point / now_price)
        (all_buy, all_buy_cost, all_sell, all_sell_price) = GetRecordKohlrabi(
            user_id, group_id
        )
        all_buy = all_buy + num
        get_point = int(round(now_price * num, 3))
        all_buy_cost = round(all_buy_cost + get_point, 3)
        change_point(user_id, group_id, now_point - get_point)
        ChangeMyKohlrabi(user_id, group_id, now_num + num)
        UpdateRecordKohlrabi(
            user_id, group_id, all_buy, all_buy_cost, all_sell, all_sell_price
        )
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {
                            "text": f"{get_user_name(user_id, group_id)},梭哈成功喵,单价{now_price},您的大头菜数目:{now_num}->{now_num + num},积分:{now_point}->{now_point - get_point}。"
                        },
                    },
                    {
                        "type": "text",
                        "data": {"text": "大头菜会在每周一的0点过期,请及时卖出喵。"},
                    },
                ],
            },
        }
    else:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {
                            "text": f"{get_user_name(user_id, group_id)},没积分?没积分不要来买大头菜喵!"
                        },
                    },
                ],
            },
        }
    await websocket.send(json.dumps(payload))


# 购买大头菜
async def BuyKohlrabi(websocket, user_id: int, group_id: int, num: int):

    now_num = GetMyKohlrabi(user_id, group_id)
    now_point = find_point(user_id)
    now_price = GetNowPrice()
    if now_point >= now_price * num:
        (all_buy, all_buy_cost, all_sell, all_sell_price) = GetRecordKohlrabi(
            user_id, group_id
        )
        all_buy = all_buy + num
        get_point = int(round(now_price * num, 3))
        all_buy_cost = round(all_buy_cost + get_point, 3)
        change_point(user_id, group_id, now_point - get_point)
        ChangeMyKohlrabi(user_id, group_id, now_num + num)
        UpdateRecordKohlrabi(
            user_id, group_id, all_buy, all_buy_cost, all_sell, all_sell_price
        )
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {
                            "text": f"{get_user_name(user_id, group_id)},买入成功喵,单价{now_price},您的大头菜数目:{now_num}->{now_num + num},积分:{now_point}->{now_point - get_point}。"
                        },
                    },
                    {
                        "type": "text",
                        "data": {"text": "大头菜会在每周一的0点过期,请及时卖出喵。"},
                    },
                ],
            },
        }
    else:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {
                            "text": f"{get_user_name(user_id, group_id)},没积分?没积分不要来买大头菜喵!"
                        },
                    },
                ],
            },
        }
    await websocket.send(json.dumps(payload))


# 获取大头菜相关统计信息
def GetRecordKohlrabi(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT all_buy,all_buy_cost,all_sell,all_sell_price FROM kohlrabi_record where user_id=? and group_id=?;",
        (
            user_id,
            group_id,
        ),
    )
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO kohlrabi_record (user_id,group_id,all_buy,all_buy_cost,all_sell,all_sell_price)VALUES(?, ?, ?, ?, ?, ?);",
            (user_id, group_id, 0, 0, 0, 0),
        )
        conn.commit()
        conn.close()
        return (0, 0, 0, 0)
    else:
        return (data[0][0], data[0][1], data[0][2], data[0][3])


# 更新大头菜相关统计信息
def UpdateRecordKohlrabi(
    user_id: int, group_id: int, all_buy, all_buy_cost, all_sell, all_sell_price
):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE kohlrabi_record SET all_buy=?,all_buy_cost=?,all_sell=?,all_sell_price=? WHERE user_id = ? AND group_id = ?;",
        (all_buy, all_buy_cost, all_sell, all_sell_price, user_id, group_id),
    )
    conn.commit()
    conn.close()


# 售出大头菜
async def SellKohlrabiAll(websocket, user_id: int, group_id: int):
    now_num = GetMyKohlrabi(user_id, group_id)
    if now_num > 0:

        num = now_num
        now_point = find_point(user_id)
        now_price = GetNowPrice()
        (all_buy, all_buy_cost, all_sell, all_sell_price) = GetRecordKohlrabi(
            user_id, group_id
        )
        get_point = int(round(now_price * num, 3))
        change_point(user_id, group_id, now_point + get_point)
        ChangeMyKohlrabi(user_id, group_id, now_num - num)
        all_sell = all_sell + num
        all_sell_price = round(all_sell_price + get_point, 3)
        UpdateRecordKohlrabi(
            user_id, group_id, all_buy, all_buy_cost, all_sell, all_sell_price
        )
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {
                            "text": f"{get_user_name(user_id, group_id)},售出成功喵,单价{now_price},你的大头菜库存:{now_num}->{now_num - num},积分:{now_point}->{now_point + get_point}喵!"
                        },
                    },
                ],
            },
        }
    else:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {
                            "text": f"{get_user_name(user_id, group_id)},大头菜数目不够喵,你当前的大头菜数目为:{now_num}个喵!"
                        },
                    },
                ],
            },
        }
    await websocket.send(json.dumps(payload))


# 售出大头菜
async def SellKohlrabi(websocket, user_id: int, group_id: int, num: int):
    now_num = GetMyKohlrabi(user_id, group_id)
    if now_num > 0 and num <= now_num:

        now_point = find_point(user_id)
        now_price = GetNowPrice()
        (all_buy, all_buy_cost, all_sell, all_sell_price) = GetRecordKohlrabi(
            user_id, group_id
        )
        get_point = int(round(now_price * num, 3))
        change_point(user_id, group_id, now_point + get_point)
        ChangeMyKohlrabi(user_id, group_id, now_num - num)
        all_sell = all_sell + num
        all_sell_price = round(all_sell_price + get_point, 3)
        UpdateRecordKohlrabi(
            user_id, group_id, all_buy, all_buy_cost, all_sell, all_sell_price
        )
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {
                            "text": f"{get_user_name(user_id, group_id)},售出成功喵,单价{now_price},你的大头菜库存:{now_num}->{now_num - num},积分:{now_point}->{now_point + get_point}喵!"
                        },
                    },
                ],
            },
        }
    else:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {
                            "text": f"{get_user_name(user_id, group_id)},大头菜数目不够喵,你当前的大头菜数目为:{now_num}个喵!"
                        },
                    },
                ],
            },
        }
    await websocket.send(json.dumps(payload))


from tools.tools import FindNum


class KohlrabiApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("大头菜贸易", "大头菜贸易")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        if "价格" in message.plainTextMessage and "大头菜" in message.plainTextMessage:
            await SayGroup(
                message.websocket,
                message.groupId,
                f"当前大头菜价格为: {GetNowPrice()} 喵,\n你的积分为 {find_point(message.senderId)} 喵。",
            )

        elif "买入" in message.plainTextMessage:
            num = FindNum(message.plainTextMessage)
            import math

            num = math.trunc(num)
            if num >= 1:
                await BuyKohlrabi(
                    message.websocket,
                    message.senderId,
                    message.groupId,
                    num,
                )
        elif "梭哈" in message.plainTextMessage:
            await ShowHand(
                message.websocket,
                message.senderId,
                message.groupId,
            )

        elif "卖出" in message.plainTextMessage:
            if "全部" in message.plainTextMessage:
                await SellKohlrabiAll(
                    message.websocket,
                    message.senderId,
                    message.groupId,
                )
        else:
            num = FindNum(message.plainTextMessage)
            import math

            num = math.trunc(num)
            if num >= 1:
                await SellKohlrabi(
                    message.websocket,
                    message.senderId,
                    message.groupId,
                    num,
                )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]
        ) and (
            HasKeyWords(message.plainTextMessage, ["买入"])
            or HasAllKeyWords(message.plainTextMessage, ["大头菜", "价格"])
            or HasKeyWords(message.plainTextMessage, ["梭哈"])
            or HasKeyWords(message.plainTextMessage, ["卖出", "全部"])
        )


# 午时已到
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


# @return (x,y)
# x=-1代表子弹错误 y=-1代表积分数目错误
# x=-2,y=-2代表赌上全部
# 装弹 <子弹数> <积分数>
def pro_str(message: str):
    if message.endswith((".", "。")):
        message = message[:-1]
    parm_list_str = message.split(" ")
    # print(parm_list_str)
    # 只输入了子弹，未输入积分
    if len(parm_list_str) == 2:
        if (int(parm_list_str[1])) > 0 and int(parm_list_str[1]) <= 5:
            return (parm_list_str[1], -2)
        else:
            return (-1, -2)
    # 只输入了装弹
    elif len(parm_list_str) == 1:
        return (-2, -2)
    else:
        if int(parm_list_str[2]) <= 0:
            y = -1
        else:
            y = parm_list_str[2]
        if int(parm_list_str[1]) <= 0 or int(parm_list_str[1]) > 5:
            x = -1
        else:
            x = parm_list_str[1]
        return (x, y)


async def russian_pve_shot(websocket, user_id: int, group_id: int, nick_name: str):
    now_shots = check_russian_pve(user_id)
    if now_shots == -1:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {"type": "at", "data": {"qq": user_id}},
                    {
                        "type": "text",
                        "data": {"text": "\n拔枪吧！午时已到！乐可可是第一神枪手喵！"},
                    },
                ],
            },
        }
        await websocket.send(json.dumps(payload))
        return
    now_choice = random.randint(1, now_shots)
    # 自己开枪中枪了
    if now_choice == 1:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {"type": "at", "data": {"qq": user_id}},
                    {
                        "type": "text",
                        "data": {
                            "text": ",对不起喵，你中枪了，乐可要拿走你的全部积分和大头菜了喵。"
                        },
                    },
                ],
            },
        }
        if GetMyKohlrabi(user_id, group_id) != 0:
            ChangeMyKohlrabi(user_id, group_id, 0)
        change_point(user_id, group_id, 0)
        delete_russian_pve(user_id)
        await websocket.send(json.dumps(payload))
        return
    now_shots = now_shots - 1
    now_choice = random.randint(1, now_shots)
    # 乐可开枪中枪了
    if now_choice == 1:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {"type": "at", "data": {"qq": user_id}},
                    {
                        "type": "text",
                        "data": {"text": ",你开了一枪未中,乐可开了一枪，中了。"},
                    },
                    {
                        "type": "text",
                        "data": {
                            "text": "\n乐可:怎么可能，你一定是作弊了喵！(恭喜{}赢了，积分翻倍)".format(
                                nick_name
                            )
                        },
                    },
                ],
            },
        }
        change_point(user_id, group_id, find_point(user_id) * 2)
        delete_russian_pve(user_id)
        await websocket.send(json.dumps(payload))
        return
    now_shots = now_shots - 1
    changed_russian_pve(user_id, now_shots)
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {
                    "type": "text",
                    "data": {
                        "text": "你开了一枪，未中；乐可开了一枪，未中。剩余子弹:{}".format(
                            now_shots
                        )
                    },
                },
            ],
        },
    }
    await websocket.send(json.dumps(payload))


async def russian_pve(websocket, user_id: int, group_id: int, nick_name: str):
    if find_point(user_id) > 0:
        now_shots = check_russian_pve(user_id)
        if now_shots == -1:
            payload = {
                "action": "send_msg_async",
                "params": {
                    "group_id": group_id,
                    "message": [
                        {"type": "at", "data": {"qq": user_id}},
                        {
                            "type": "text",
                            "data": {
                                "text": "\n{},拔枪吧！午时已到！乐可可是第一神枪手喵！".format(
                                    nick_name
                                )
                            },
                        },
                    ],
                },
            }
        else:
            payload = {
                "action": "send_msg_async",
                "params": {
                    "group_id": group_id,
                    "message": [
                        {
                            "type": "text",
                            "data": {
                                "text": "{},你已经在乐可在决斗了喵，快开抢吧！".format(
                                    nick_name
                                )
                            },
                        },
                    ],
                },
            }
    else:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {
                            "text": "{},没积分？没积分不要来挑战乐可喵。".format(
                                nick_name
                            )
                        },
                    },
                ],
            },
        }
    await websocket.send(json.dumps(payload))


#
async def russian(websocket, message: str, user_id: int, group_id: int):
    (bullet, point) = pro_str(message)
    if bullet == -1 or point == -1:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {"type": "at", "data": {"qq": user_id}},
                    {
                        "type": "text",
                        "data": {"text": "子弹数目必须在1~5，积分不能为负数。"},
                    },
                ],
            },
        }
    elif bullet != -1 and point == -2:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {"type": "at", "data": {"qq": user_id}},
                    {
                        "type": "text",
                        "data": {
                            "text": "装入{}颗子弹;未输入积分，默认全部积分：{}。".format(
                                bullet, find_point(user_id)
                            )
                        },
                    },
                ],
            },
        }
    elif point == -2 and bullet == -2:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {"type": "at", "data": {"qq": user_id}},
                    {
                        "type": "text",
                        "data": {
                            "text": "经典模式，1颗子弹和全部积分:{}。".format(
                                find_point(user_id)
                            )
                        },
                    },
                ],
            },
        }
    else:
        user_point = find_point(user_id)
        if int(user_point) > int(point):
            payload = {
                "action": "send_msg_async",
                "params": {
                    "group_id": group_id,
                    "message": [
                        {"type": "at", "data": {"qq": user_id}},
                        {
                            "type": "text",
                            "data": {
                                "text": "子弹上膛，{}颗子弹，{}积分。".format(
                                    bullet, point
                                )
                            },
                        },
                    ],
                },
            }
        else:
            payload = {
                "action": "send_msg_async",
                "params": {
                    "group_id": group_id,
                    "message": [
                        {"type": "at", "data": {"qq": user_id}},
                        {"type": "text", "data": "积分不足，无法上膛。"},
                    ],
                },
            }
    await websocket.send(json.dumps(payload))


class LunchTimeApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("午时已到", "午时已到")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        if HasKeyWords(
            message.plainTextMessage,
            ["挑战你", "午时已到"],
        ):
            await russian_pve(
                message.websocket,
                message.senderId,
                message.groupId,
                get_user_name(message.senderId, message.groupId),
            )

        elif HasKeyWords(
            message.plainTextMessage,
            ["开枪"],
        ):
            await russian_pve_shot(
                message.websocket,
                message.senderId,
                message.groupId,
                get_user_name(message.senderId, message.groupId),
            )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return (
            HasKeyWords(
                message.plainTextMessage,
                ["挑战你", "午时已到"],
            )
            or HasKeyWords(
                message.plainTextMessage,
                ["开枪"],
            )
        ) and HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]  # type: ignore
        )


# 梗图统计
from tools.tools import GetDirSizeByUnit


async def MemeStatistics(websocket, group_id: int):
    all_file = find_all_file(load_setting("meme_path", ""))
    num, unit = GetDirSizeByUnit(load_setting("meme_path", ""))
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {
                    "type": "text",
                    "data": {
                        "text": f"共有{len(all_file)}张图片,占用{num}{unit}空间喵!"
                    },
                },
            ],
        },
    }
    await websocket.send(json.dumps(payload))


def find_all_file(path: str):
    s = []
    dir_path = "{}/**/*.*".format(path)
    for file in glob.glob(dir_path, recursive=True):
        # print(file)
        s.append(file)
    return s


class MemeStatisticsApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("梗图统计", "统计梗图库存")
        super().__init__(applicationInfo, 65, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await MemeStatistics(message.websocket, message.groupId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]  # type: ignore
        ) and HasAllKeyWords(message.plainTextMessage, ["统计", "梗图"])


# TODO 个人统计应用
class PersonalStatisticsApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("个人统计", "统计个人库存")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        pass

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]  # type: ignore
        ) and HasAllKeyWords(message.plainTextMessage, ["统计"])


# 排名应用
import matplotlib.pyplot as plt
from plottable import Table
import pandas as pd

from tools.tools import load_static_setting


# 群友水群次数表格
def ShowTableByBase64(data):
    plt.rcParams["font.sans-serif"] = load_static_setting(
        "font", ["Unifont"]
    )  # 设置字体
    plt.rcParams["axes.unicode_minus"] = False  # 正常显示负号
    table = pd.DataFrame(data)
    fig, ax = plt.subplots()
    table = table.set_index("排名")
    Table(table)
    plt.title("水群排名")
    plt.savefig("figs/chat_table.png", dpi=460)
    plt.close()
    with open("figs/chat_table.png", "rb") as image_file:
        image_data = image_file.read()
    return base64.b64encode(image_data)


# 统计生涯水群次数
async def GetLifeChatRecord(websocket, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id,all_num FROM ChatRecord WHERE group_id=? ORDER BY all_num DESC ;",
        (group_id,),
    )
    data = cur.fetchall()
    num: int = 0
    if len(data) == 0:
        return
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


# 统计今日水群次数
async def GetNowChatRecord(websocket, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id,today_num FROM ChatRecord WHERE group_id=? and today=? ORDER BY today_num DESC ;",
        (
            group_id,
            GetNowDay(),
        ),
    )
    data = cur.fetchall()
    num: int = 0
    if len(data) == 0:
        return
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


class User_point:
    user_id: int
    point: int
    time: int

    def __init__(self, user_id: int, point: int, time: int):
        self.user_id = user_id
        self.point = point
        self.time = time


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


from function.group_operation import IsInGroup
from function.datebase_user import get_user_info

from tools.tools import load_static_setting


# 群友积分统计表格
def ShowRankingByBase64(data):
    plt.rcParams["font.sans-serif"] = load_static_setting(
        "font", ["Unifont"]
    )  # 设置字体
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


def find_value(type: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM rankings where type=? and group_id=?", (type, group_id))
    data = cur.fetchall()
    if len(data) == 0:
        return (False, Ranking(-1, -1, -1, -1, -1))
    else:
        ranking = Ranking(data[0][0], data[0][1], data[0][2], data[0][3], data[0][4])
        return (True, ranking)


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
        if IsInGroup(points_info.user_id, group_id):
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


class RankingApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("排名", "统计个人排名")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        if HasAllKeyWords(
            message.plainTextMessage,
            ["生涯", "水群", "排名"],
        ):
            await GetLifeChatRecord(message.websocket, message.groupId)
        elif "水群排名" in message.plainTextMessage:
            await GetNowChatRecord(message.websocket, message.groupId)
        elif "排名" in message.plainTextMessage:
            await ranking_point_payload(message.websocket, message.groupId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]  # type: ignore
        ) and (
            HasAllKeyWords(message.plainTextMessage, ["生涯", "水群", "排名"])
            or HasKeyWords(message.plainTextMessage, ["水群排名", "排名"])
        )


# 抽签应用
# 抽签
async def DrawingLottery(websocket, user_id: int, group_id: int):
    r = requests.get("https://api.tangdouz.com/a/ccscq.php", timeout=60)
    # print(r.text)
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {
                    "type": "text",
                    "data": {"text": "\n{}".format(r.text.replace("\\r", "\r"))},
                },
            ],
        },
    }
    # print(payload)
    await websocket.send(json.dumps(payload))


class DrawLotteryApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("抽签", "抽签")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await DrawingLottery(message.websocket, message.senderId, message.groupId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可"), "抽签"]
        )


# 积分帮助
class PointHelpApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("积分帮助", "积分帮助")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await SayGroup(
            message.websocket,
            message.groupId,
            f"{get_user_name(message.senderId, message.groupId)},积分可通过抽奖、签到、在有权限的群水群和大头菜贸易获得喵。",
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可"), "积分帮助"]
        )


# 跑路或者梭哈


# 梭哈或者跑路
async def RunOrShot(websocket, user_id, group_id):
    list = [0, 1]
    _ = random.choice(list)
    if _ == 0:
        __ = random.choice(list)
        if __ == 0:
            await SayGroup(
                websocket,
                group_id,
                f"{get_user_name(user_id, group_id)},梭哈失败,跑路失败喵!(清空全部积分和大头菜并施加100次艾特惩罚)",
            )
            if GetMyKohlrabi(user_id, group_id) != 0:
                ChangeMyKohlrabi(user_id, group_id, 0)
            change_point(user_id, group_id, find_point(user_id) * 0)
            AddAtPunishList(user_id, group_id, 100)
        else:
            await SayGroup(
                websocket,
                group_id,
                f"{get_user_name(user_id, group_id)},梭哈失败,跑路成功喵!(清空全部积分和大头菜,踢了!?)",
            )
            if GetMyKohlrabi(user_id, group_id) != 0:
                ChangeMyKohlrabi(user_id, group_id, 0)
            change_point(user_id, group_id, find_point(user_id) * 0)
    else:
        await SayGroup(
            websocket,
            group_id,
            f"{get_user_name(user_id, group_id)},梭哈成功,积分和大头菜翻10倍喵.",
        )
        change_point(user_id, group_id, find_point(user_id) * 10)
        ChangeMyKohlrabi(user_id, group_id, GetMyKohlrabi(user_id, group_id) * 10)


class RunOrShotApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("跑路或者梭哈", "跑路或者梭哈")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await RunOrShot(message.websocket, message.senderId, message.groupId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]
        ) and HasAllKeyWords(message.plainTextMessage, ["跑路", "梭哈"])


# 反击应用
class DefenseApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("反击", "反击", False)
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        result = re.search(r"\d+", message.plainTextMessage)
        if result != None:
            qq = int(result.group())
            if qq is not None:
                await SayAndAt(
                    message.websocket,
                    qq,
                    message.groupId,
                    f"惩罚性艾特{load_setting('defense_times',50)}次。",
                )
                AddAtPunishList(
                    qq,
                    message.groupId,
                    load_setting("defense_times", 50),
                )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]
        ) and HasAllKeyWords(message.plainTextMessage, ["反击"])


# 睡眠套餐应用
from tools.tools import GetSleepSeconds


class IWantToSleepApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("反击", "反击", False)
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await SayGroup(
            message.websocket,
            message.groupId,
            f"{get_user_name(message.senderId,message.groupId)}睡眠套餐已开启,明天早上6点见。",
        )
        await ban_new(
            message.websocket, message.senderId, message.groupId, GetSleepSeconds()
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return (
            HasKeyWords(message.plainTextMessage, [load_setting("bot_name", "乐可")])
            and HasAllKeyWords(message.plainTextMessage, ["睡眠套餐"])
            and BotIsAdmin(message.groupId)
            and not IsAdmin(message.senderId, message.groupId)
        )


# 涩图兑换


# 发送一张绝对涩的涩图
async def sex_img(websocket, user_id: int, group_id: int):
    now_point = find_point(user_id)
    if now_point < 500000:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {
                            "text": "{},你的积分不够喵,需要500000积分的喵,目前你的积分为{}喵,还差{}积分喵。".format(
                                get_user_name(
                                    user_id,
                                    group_id,
                                ),
                                now_point,
                                500000 - now_point,
                            )
                        },
                    },
                ],
            },
        }
    else:
        change_point(
            user_id,
            group_id,
            now_point - 500000,
        )
        path = "res/sex_img.jpg"
        with open(path, "rb") as image_file:
            image_data = image_file.read()
        image_base64 = base64.b64encode(image_data)
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {
                            "text": "{},乐可收到你的积分了喵,售出不退喵,积分离柜概不负责喵。你的积分{}->{}喵。".format(
                                get_user_name(
                                    user_id,
                                    group_id,
                                ),
                                now_point,
                                now_point - 500000,
                            )
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


class SexImageApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("涩图兑换", "涩图兑换")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await sex_img(message.websocket, message.senderId, message.groupId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]
        ) and HasAllKeyWords(message.plainTextMessage, ["兑换", "涩图"])


# 丢骰子
class GetRadomNum1to6Application(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("丢骰子", "丢骰子")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await SayGroup(
            message.websocket,
            message.groupId,
            f"你的骰子结果是{random.randint(1,6)}",
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]
        ) and HasAllKeyWords(message.plainTextMessage, ["丢骰子"])


# COS图
# 涩涩
async def get_cos(websocket, user_id: int, group_id: int):
    r = requests.get("https://api.tangdouz.com/hlxmt.php", timeout=60)
    text = r.text.split("±")
    text = list(filter(None, text))
    # print(text)
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {
                    "type": "text",
                    "data": {"text": "\n{}".format(text[0])},
                },
            ],
        },
    }
    for i in range(1, len(text)):
        payload["params"]["message"].append(
            {"type": "image", "data": {"file": text[i][4:]}},
        )
    print(payload)
    payload["params"]["message"].append(
        {"type": "text", "data": {"text": "随机手机分辨率美图\n"}},
    )
    r = requests.get(
        "https://api.vvhan.com/api/wallpaper/mobileGirl?type=json", timeout=60
    )
    json_data = json.loads(r.text)
    if "url" in json_data:
        payload["params"]["message"].append(
            {"type": "image", "data": {"file": json_data["url"]}},
        )
    payload["params"]["message"].append(
        {"type": "text", "data": {"text": "随机PC分辨率美图\n"}},
    )
    r = requests.get("https://api.vvhan.com/api/wallpaper/pcGirl?type=json", timeout=60)
    json_data = json.loads(r.text)
    if "url" in json_data:
        payload["params"]["message"].append(
            {"type": "image", "data": {"file": json_data["url"]}},
        )
    await websocket.send(json.dumps(payload))


class GetCosImageApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("获取COS图", "获取COS图")
        super().__init__(applicationInfo, 30, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await get_cos(message.websocket, message.senderId, message.groupId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]
        ) and HasKeyWords(message.plainTextMessage, ["cos", "COS", "涩图"])


# 自助退群应用
class SeeYouAgain(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("再也不见", "自助退群")
        super().__init__(applicationInfo, 30, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        if IsAdmin(message.senderId, message.groupId):
            await SayGroup(
                message.websocket,
                message.groupId,
                f"{get_user_name(message.senderId, message.groupId)},你是管理员，不能自助退群喵。",
            )
        else:
            await kick_member(message.websocket, message.senderId, message.groupId)
            await ReplySay(
                message.websocket,
                message.groupId,
                message.messageId,
                "再见,再也不见。",
            )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return (
            HasKeyWords(message.plainTextMessage, [load_setting("bot_name", "乐可")])
            and HasKeyWords(message.plainTextMessage, ["再也不见", "重开"])
            and BotIsAdmin(message.groupId)
        )


# 二次元美图应用
# 随机二次元美图
async def radom_waifu(websocket, user_id: int, group_id: int):
    r = requests.get("https://api.tangdouz.com/abz/dm.php", timeout=60)
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {"type": "image", "data": {"file": r.text}},
            ],
        },
    }
    await websocket.send(json.dumps(payload))


class GetWaiFuApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("二次元应用", "获取随机二次元美图")
        super().__init__(applicationInfo, 30, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await radom_waifu(message.websocket, message.senderId, message.groupId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]
        ) and HasKeyWords(message.plainTextMessage, ["二次元"])


# 三次元美图应用
from random import choice


# 随机三次元美图
async def radom_real(websocket, user_id: int, group_id: int):
    url1 = requests.get("https://api.tangdouz.com/mn.php", timeout=60)
    url2 = requests.get(
        choice(["https://api.tangdouz.com/mt.php", "https://api.tangdouz.com/mt1.php"]),
        timeout=60,
    )
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {"type": "image", "data": {"file": url1.text}},
                {"type": "image", "data": {"file": url2.text}},
            ],
        },
    }
    await websocket.send(json.dumps(payload))


class GetRealWifeApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("三次元应用", "获取随机三次元美图")
        super().__init__(applicationInfo, 30, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await radom_real(message.websocket, message.senderId, message.groupId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]
        ) and HasKeyWords(message.plainTextMessage, ["三次元"])


# 随机一言应用


# 随机一言
async def one_word(websocket, user_id: int, group_id: int):
    url_list = [
        "https://api.tangdouz.com/aqgy.php",
        "https://api.tangdouz.com/sjyy.php",
        "https://api.tangdouz.com/a/one.php",
    ]
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {
                    "type": "text",
                    "data": {
                        "text": "\n{}".format(
                            requests.get(choice(url_list), timeout=60).text
                        )
                    },
                },
            ],
        },
    }
    await websocket.send(json.dumps(payload))


class RadomOneWordApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("随机一言", "获取随机一言")
        super().__init__(applicationInfo, 30, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await one_word(message.websocket, message.senderId, message.groupId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]
        ) and HasKeyWords(message.plainTextMessage, ["一言"])


# 随机HTTP猫猫
async def send_radom_http_cat(websocket, group_id: int):
    http_code = [
        100,
        101,
        200,
        201,
        202,
        203,
        204,
        205,
        206,
        300,
        301,
        302,
        303,
        304,
        305,
        306,
        307,
        400,
        401,
        402,
        403,
        404,
        405,
        406,
        407,
        408,
        409,
        410,
        411,
        412,
        413,
        414,
        415,
        416,
        417,
        418,
        500,
        501,
        502,
        503,
        504,
        505,
    ]
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": {
                "type": "image",
                "data": {
                    "file": "https://http.cat/{}".format(
                        http_code[random.randint(0, len(http_code) - 1)]
                    )
                },
            },
        },
    }
    await websocket.send(json.dumps(payload))


class RadomHttpCatApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("随机HTTP猫猫", "获取随机HTTP猫猫")
        super().__init__(applicationInfo, 30, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await send_radom_http_cat(message.websocket, message.groupId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]
        ) and HasKeyWords(message.plainTextMessage, ["随机HTTP猫猫", "随机http猫猫"])


# 运势应用
from datetime import date


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
async def luck_dog(websocket, user_id: int, group_id: int):
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": "{},{}。".format(
                get_user_name(user_id, group_id),
                ys_simple((date.today().day * user_id) % 100),
            ),
        },
    }
    await websocket.send(json.dumps(payload))


class LuckDogApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("每日运势", "获取每日运势")
        super().__init__(applicationInfo, 30, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await luck_dog(message.websocket, message.senderId, message.groupId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]
        ) and HasKeyWords(message.plainTextMessage, ["运势"])


# # 签到应用
# async def DailyCheckIn(websocket, user_id: int, group_id: int):
#     sender_name = get_user_name(user_id, group_id)
#     result = check_in(user_id, group_id)
#     if result[0] == 1:
#         payload = {
#             "action": "send_msg_async",
#             "params": {
#                 "group_id": group_id,
#                 "message": "{},签到成功,您当前的积分为:{}。".format(
#                     sender_name, result[1]
#                 ),
#             },
#         }
#     else:
#         payload = {
#             "action": "send_msg_async",
#             "params": {
#                 "group_id": group_id,
#                 "message": "{},你今天已经签过到了,明天再来吧!您当前的积分为:{}。".format(
#                     sender_name, result[1]
#                 ),
#             },
#         }
#     await websocket.send(json.dumps(payload))


# class DailyCheckInApplication(GroupMessageApplication):
#     def __init__(self):
#         applicationInfo = ApplicationInfo("签到", "签到")
#         super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

#     async def process(self, message: GroupMessageInfo) -> None:
#         # 处理消息
#         await DailyCheckIn(message.websocket, message.senderId, message.groupId)

#     def judge(self, message: GroupMessageInfo) -> bool:
#         """判断是否触发应用"""
#         return HasKeyWords(
#             message.plainTextMessage, [load_setting("bot_name", "乐可")]
#         ) and HasKeyWords(message.plainTextMessage, ["签到"])


# 疯狂星期四应用


# kfcv我50彩蛋
async def KFCVME50(websocket, group_id: int):
    r = requests.get("https://api.shadiao.pro/kfc", timeout=60)
    data = json.loads(r.text)
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "text", "data": {"text": data["data"]["text"]}},
            ],
        },
    }
    await websocket.send(json.dumps(payload))


class KFCVME50Application(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("疯狂星期四应用", "疯狂星期四应用")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await KFCVME50(message.websocket, message.groupId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]
        ) and HasKeyWords(message.plainTextMessage, ["V我50", "v我50"])


# 塔罗牌应用


# 塔罗牌
async def ReturnTrarotCard(websocket, user_id: int, group_id: int):
    r = requests.get("https://api.tangdouz.com/tarot.php", timeout=60)
    text = r.text.split("±")
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {
                    "type": "text",
                    "data": {"text": "\n{}".format(text[0].split("\\r")[1])},
                },
                {"type": "image", "data": {"file": text[1][4:]}},
                {
                    "type": "text",
                    "data": {
                        "text": "{}{}".format(
                            text[2].split("\\r")[0], text[2].split("\\r")[1]
                        )
                    },
                },
            ],
        },
    }
    # print(payload)
    await websocket.send(json.dumps(payload))


class TarotApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("塔罗牌应用", "塔罗牌应用")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        await ReturnTrarotCard(message.websocket, message.senderId, message.groupId)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可"), "塔罗牌"]
        )


# 晚安应用
class GoodNightApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("晚安应用", "晚安应用")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        now_hour = int(datetime.now().strftime("%H"))
        if now_hour >= 22 or now_hour < 6:
            if IsAdmin(message.senderId, message.groupId):
                await SayGroup(
                    message.websocket,
                    message.groupId,
                    f"{get_user_name(message.senderId, message.groupId)},晚安，好梦喵。(∪.∪ )...zzz",
                )

            else:
                await SayGroup(
                    message.websocket,
                    message.groupId,
                    f"{get_user_name(message.senderId, message.groupId)},明天早上六点见喵,晚安，好梦喵。(∪.∪ )...zzz",
                )
                await ban_new(
                    message.websocket,
                    message.senderId,
                    message.groupId,
                    GetSleepSeconds(),
                )

        elif now_hour < 22:
            await SayGroup(
                message.websocket,
                message.groupId,
                f"{get_user_name(message.senderId, message.groupId)},还没到晚上10点喵,睡的有点早喵。",
            )
        elif now_hour >= 22 and now_hour < 6:
            await SayGroup(
                message.websocket,
                message.groupId,
                f"{get_user_name(message.senderId, message.groupId)},夜深了，早点休息喵。(∪.∪ )...zzz",
            )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可"), "晚安"]
        )


# 随机猫猫
class RandomCatApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("随机猫猫", "随机猫猫")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        r = requests.get("https://api.thecatapi.com/v1/images/search", timeout=60)
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": message.groupId,
                "message": [
                    {"type": "image", "data": {"file": r.json()[0]["url"]}},
                ],
            },
        }
        await message.websocket.send(json.dumps(payload))

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可"), "猫猫"]
        )


# 随机猫猫动图
class RandomCatGifApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("随机猫猫动图", "随机猫猫动图")
        super().__init__(applicationInfo, 75, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": message.groupId,
                "message": [
                    {"type": "image", "data": {"file": "https://edgecats.net/"}},
                ],
            },
        }
        await message.websocket.send(json.dumps(payload))

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可"), "猫猫动图"]
        )


# 看世界应用
class LookWorldApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("随机猫猫动图", "随机猫猫动图")
        super().__init__(applicationInfo, 75, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        r = requests.get("https://api.tangdouz.com/60.php", timeout=60)
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": message.groupId,
                "message": [
                    {"type": "at", "data": {"qq": message.senderId}},
                    {"type": "image", "data": {"file": r.text}},
                ],
            },
        }
        await message.websocket.send(json.dumps(payload))

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可"), "看世界"]
        )


# 灭霸应用
from function.database_group import GetAllGroupMemberId


async def set_qq_avatar(websocket, file_dir: str):
    with open(file_dir, "rb") as image_file:
        image_data = image_file.read()
    payload = {
        "action": "set_qq_avatar",
        "params": {"file": "base64://" + base64.b64encode(image_data).decode("utf-8")},
    }
    await websocket.send(json.dumps(payload))


class TimelyCheckTanosApplication(MetaMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo(
            "定期检测打响指有效性", "定期检测打响指有效性", False
        )
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: MetaMessageInfo):
        """处理元消息"""
        thanos_queue = load_setting("thanos_queue", [])
        for i in thanos_queue:
            if time.time() - i["thanosTime"] > 300:
                await SayGroup(
                    message.websocket,
                    i["groupId"],
                    f"{load_setting("bot_name", "乐可")}不是紫薯精喵。",
                )
                thanos_queue.remove(i)
        if len(thanos_queue) == 0:
            await set_qq_avatar(message.websocket, "res/leike.jpg")
            dump_setting("is_thanos", False)
        dump_setting("thanos_queue", thanos_queue)

    def judge(self, message: MetaMessageInfo) -> bool:
        """判断是否触发应用"""
        return (
            len(load_setting("thanos_queue", [])) > 0
            and message.metaEventType == MetaEventType.HEART_BEAT
            and load_setting("is_thanos", False)
        )


class ThanosApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("打响指应用", "清除一半人")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        if HasKeyWords(message.plainTextMessage, ["打响指"]):
            await SayGroup(
                message.websocket,
                message.groupId,
                f"{get_user_name(message.senderId,message.groupId,)},你确定吗？此功能会随机清除一半的群友,如果确定的话,请在5分钟内说“{load_setting("bot_name", "乐可")},清楚明白”。如果取消的话,请说“{load_setting("bot_name", "乐可")},取消”。",
            )
            await set_qq_avatar(message.websocket, "res/leike_red.jpg")
            thanos_queue = load_setting("thanos_queue", [])
            thanos_queue.append({"groupId": message.groupId, "thanosTime": time.time()})
            dump_setting("thanos_queue", thanos_queue)
            dump_setting("is_thanos", True)
        elif HasKeyWords(message.plainTextMessage, ["清楚明白"]) and load_setting(
            "is_thanos", False
        ):
            thanos_queue = load_setting("thanos_queue", [])
            if random.random() < 0.5:
                for i in GetAllGroupMemberId(message.groupId):
                    await kick_member(message.websocket, i, message.groupId)
            for i in thanos_queue:
                if i["groupId"] == message.groupId:
                    thanos_queue.remove(i)
                    break
            dump_setting("thanos_queue", thanos_queue)
            if len(thanos_queue) == 0:
                await set_qq_avatar(message.websocket, "res/leike.jpg")
                dump_setting("is_thanos", False)

        elif HasKeyWords(message.plainTextMessage, ["取消"]) and load_setting(
            "is_thanos", False
        ):
            # await set_qq_avatar(message.websocket, "res/leike.jpg")
            await SayGroup(
                message.websocket,
                message.groupId,
                f"{load_setting("bot_name", "乐可")}不是紫薯精喵。",
            )
            thanos_queue = load_setting("thanos_queue", [])
            for i in thanos_queue:
                if i["groupId"] == message.groupId:
                    thanos_queue.remove(i)
                    break
            dump_setting("thanos_queue", thanos_queue)
            if len(thanos_queue) == 0:
                await set_qq_avatar(message.websocket, "res/leike.jpg")
                dump_setting("is_thanos", False)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return (
            HasAllKeyWords(message.plainTextMessage, [load_setting("bot_name", "乐可")])
            and HasKeyWords(message.plainTextMessage, ["打响指", "清楚明白", "取消"])
            and IsAdmin(message.senderId, message.groupId)
            and BotIsAdmin(message.groupId)
        )


# 环境温度应用
import re
import subprocess


class GetTemperatureApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("获取环境温度", "获取环境温度")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理消息
        command = "sensors"
        result = subprocess.check_output(command, shell=True, text=True)
        pattern = r"\d+\.\d+"
        matches = re.findall(pattern, str(result))

        await SayGroup(
            message.websocket,
            message.groupId,
            f"CPU:{matches[0]}/{matches[1]}°C,GPU:{matches[2]}°C,环境温度:{"错误,请检查传感器"}",
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可"), "环境温度"]
        )


# 早上好应用
class OldGoodMorningApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("早上好应用", "早上好应用")
        super().__init__(applicationInfo, 20, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        now_hour = int(datetime.now().strftime("%H"))
        if now_hour < 10:
            await SayGroup(
                message.websocket,
                message.groupId,
                f"{get_user_name(message.senderId, message.groupId)},早上好喵ヾ(•ω•`)o,今天也是元气满满的一天喵！",
            )
        else:
            await SayGroup(
                message.websocket,
                message.groupId,
                f"{get_user_name(message.senderId, message.groupId)},现在已经不早了喵！",
            )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可"), "早"]
        )


# 喜报悲报应用
class HappySadNewsApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("喜报悲报应用", "喜报悲报应用")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        if HasKeyWords(message.plainTextMessage, ["喜报"]):
            text = re.findall(
                r"喜报\s*([\s\S]*)$",
                message.plainTextMessage,
            )
            if len(text) != 0:
                payload = {
                    "action": "send_msg_async",
                    "params": {
                        "group_id": message.groupId,
                        "message": [
                            {
                                "type": "image",
                                "data": {
                                    "file": f"https://api.tangdouz.com/wz/xb.php?nr={text[0]}"
                                },
                            },
                        ],
                    },
                }
                await message.websocket.send(json.dumps(payload))
        elif HasKeyWords(message.plainTextMessage, ["悲报"]):
            text = re.findall(
                r"悲报\s*([\s\S]*)$",
                message.plainTextMessage,
            )
            if len(text) != 0:
                payload = {
                    "action": "send_msg_async",
                    "params": {
                        "group_id": message.groupId,
                        "message": [
                            {
                                "type": "image",
                                "data": {
                                    "file": f"https://www.oexan.cn/API/beibao.php?msg={text[0]}"
                                },
                            },
                        ],
                    },
                }
                await message.websocket.send(json.dumps(payload))

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]
        ) and HasKeyWords(message.plainTextMessage, ["喜报", "悲报"])


# 答案之书应用
class AnswerBookApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("答案之书应用", "答案之书应用")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        r = requests.get("https://api.tangdouz.com/answer.php", timeout=60)
        await ReplySay(message.websocket, message.groupId, message.messageId, r.text)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可"), "答案之书"]
        )


# 获取系统状态应用

from tools.tools import load_static_setting


# 获取系统状态
def ShowSystemInfoTableByBase64():
    import matplotlib.pyplot as plt
    from plottable import Table
    import pandas as pd
    import base64
    import psutil
    import platform

    plt.rcParams["font.sans-serif"] = load_static_setting(
        "font", ["Unifont"]
    )  # 设置字体
    plt.rcParams["axes.unicode_minus"] = False  # 正常显示负号
    data = {"项目": [], "值": []}
    if platform.system() == "Linux":
        info = platform.freedesktop_os_release()
        data["项目"].append("操作系统名称")
        data["值"].append(info["NAME"])
        data["项目"].append("操作系统版本")
        data["值"].append(info["VERSION"])
    elif platform.system() == "Windows":
        os_name = platform.system()
        data["项目"].append("操作系统名称")
        data["值"].append(f"{os_name}")
        os_version = platform.version()
        data["项目"].append("操作系统版本")
        data["值"].append(f"{os_version}")
    # 获取计算机的处理器名称
    data["项目"].append("处理器名称")
    data["值"].append(platform.processor())
    # 获取计算机的处理器架构
    data["项目"].append("处理器架构")
    data["值"].append(platform.architecture())
    mem = psutil.virtual_memory()
    # 系统总计内存
    zj = float(mem.total) / 1024 / 1024
    # 系统已经使用内存
    ysy = float(mem.used) / 1024 / 1024
    # 系统空闲内存
    kx = float(mem.free) / 1024 / 1024
    data["项目"].append("系统总计内存")
    data["值"].append(f"{zj:.4f} MB")
    data["项目"].append("系统已经使用内存")
    data["值"].append(f"{ysy:.4f} MB")
    data["项目"].append("系统空闲内存")
    data["值"].append(f"{kx:.4f} MB")
    # 查看cpu逻辑个数的信息
    data["项目"].append("逻辑CPU个数")
    data["值"].append(psutil.cpu_count())
    # 查看cpu物理个数的信息
    data["项目"].append("物理CPU个数")
    data["值"].append(psutil.cpu_count(logical=False))
    # CPU的使用率
    cpu = (str(psutil.cpu_percent(1))) + "%"
    data["项目"].append("CPU使用率")
    data["值"].append((str(psutil.cpu_percent(1))) + "%")
    dk = psutil.disk_usage("/")
    # 总磁盘
    total = dk.total / 1024 / 1024 / 1024
    used = dk.used / 1024 / 1024 / 1024
    free = dk.free / 1024 / 1024 / 1024
    data["项目"].append("系统总计磁盘")
    data["值"].append(f"{total:0.3f} GB")
    data["项目"].append("系统已经使用磁盘")
    data["值"].append(f"{used:0.3f} GB")
    data["项目"].append("系统空闲磁盘")
    data["值"].append(f"{free:0.3f} GB")
    data["项目"].append("磁盘使用率")
    data["值"].append(f"{dk.percent:0.1f}%")
    # 发送数据包
    data["项目"].append("发送数据字节")
    data["值"].append(f"{psutil.net_io_counters().bytes_sent} bytes")
    # 接收数据包
    data["项目"].append("发送数据字节")
    data["值"].append(f"{psutil.net_io_counters().bytes_recv} bytes")
    table = pd.DataFrame(data)
    table = table.set_index("项目")
    fig, ax = plt.subplots()
    Table(table)
    plt.title("系统状态")
    plt.savefig("figs/system_table.png", dpi=460)
    # plt.show()
    plt.close()
    with open("figs/system_table.png", "rb") as image_file:
        image_data = image_file.read()
    return base64.b64encode(image_data)


class GetSystemStatusApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("获取系统状态应用", "获取系统状态应用")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": message.groupId,
                "message": [],
            },
        }
        payload["params"]["message"].append(
            {
                "type": "image",
                "data": {
                    "file": "base64://" + ShowSystemInfoTableByBase64().decode("utf-8")
                },
            }
        )
        await message.websocket.send(json.dumps(payload))

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]
        ) and HasKeyWords(message.plainTextMessage, ["系统状态", "系统信息", "状态信息", "status"])


# 获取IP应用


# 获取本机局域网IP
def GetLocalIP():
    from netifaces import interfaces, ifaddresses, AF_INET

    ip_addrs = []
    for ifaceName in interfaces():
        addresses = [
            i["addr"]
            for i in ifaddresses(ifaceName).setdefault(
                AF_INET, [{"addr": "No IP addr"}]  # type: ignore
            )
        ]
        if addresses != ["No IP addr"]:
            ip_addrs.append(addresses[0])
    # print(ip_addrs)
    return ip_addrs


class GetSystemIPApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("获取IP应用", "获取IP应用")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        ip = requests.get("https://api.ipify.org?format=json", timeout=60).json()
        await SayGroup(
            message.websocket,
            message.groupId,
            f"本机IP:{GetLocalIP()}",
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可")]
        ) and HasKeyWords(message.plainTextMessage, ["获取IP", "IP地址", "获取ip", "ip地址"])


# 讲冷笑话应用
class JokeApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("讲冷笑话应用", "讲冷笑话应用")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        r = requests.get("https://api.vvhan.com/api/text/joke")
        await SayGroup(message.websocket, message.groupId, r.text)

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可"), "笑话"]
        )


# 乐可可爱应用
from tools.tools import HasNoneKeyWords


class CuteApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("卖萌应用", "卖萌应用")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        list = ["res/cute3.gif", "res/cute4.gif", "res/cute5.gif", "res/cute6.gif"]
        path = random.choice(list)
        logging.info("有人夸乐可可爱。")
        with open(path, "rb") as image_file:
            image_data = image_file.read()
        image_base64 = base64.b64encode(image_data)
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": message.groupId,
                "message": [
                    {
                        "type": "image",
                        "data": {"file": "base64://" + image_base64.decode("utf-8")},
                    },
                ],
            },
        }
        await message.websocket.send(json.dumps(payload))

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可"), "可爱"]
        ) and HasNoneKeyWords(message.plainTextMessage, ["可乐"])


# 私聊功能
from function.say import SayPrivte
from data.application.private_message_application import PrivateMessageApplication


# 私聊聊天功能
from function.chat import PrivateChatNoContext
from data.message.private_message_info import PrivateMesssageInfo


class PrivateChatApplication(PrivateMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("私聊聊天应用", "私聊聊天应用")
        super().__init__(
            applicationInfo, 0, False, ApplicationCostType.HIGH_TIME_HIGH_PERFORMANCE
        )

    async def process(self, message: PrivateMesssageInfo) -> None:
        await SayPrivte(
            message.websocket,
            message.senderId,
            PrivateChatNoContext(message.plainTextMessage),
        )

    def judge(self, message: PrivateMesssageInfo) -> bool:
        """判断是否触发应用"""
        return True


# 偷偷加积分应用
class StealthyPointsApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("偷偷加积分应用", "偷偷加积分应用", False)
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: PrivateMesssageInfo) -> None:
        # 在这里实现偷偷加积分的逻辑
        result = re.search(r"\d+", message.plainTextMessage)
        if result != None:
            now_point = find_point(message.senderId)
            change_point(message.senderId, 0, now_point + int(result.group()))
            await SayPrivte(
                message.websocket,
                message.senderId,
                f"充值成功,积分{now_point}->{now_point +  int(result.group())}。",
            )

    def judge(self, message: PrivateMesssageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可"), "积分"]
        ) and message.senderId in load_setting("developers_list", [])


# 发送日志应用

import yagmail
from tools.tools import GetLogTime


# 发送日志文件到邮箱
def send_log_email():
    email = load_setting("email", {"user": "", "password": "", "host": ""})
    # 连接邮箱服务器 发送方邮箱+授权码+邮箱服务地址
    yag = yagmail.SMTP(
        user=email["user"],
        password=email["password"],
        host=email["host"],
        encoding="GBK",
    )
    # 邮件正文 支持html，支持上传附件
    now = GetLogTime()
    log_path = f"log/{now}.log"
    content = [f"{GetLogTime()}的日志"]
    # logging.info(f"发送{log_path}日志文件到邮箱")
    print(f"发送{log_path}日志文件到邮箱")
    yag.send(
        email["rev_email"],
        "运行日志",
        content,
        [
            log_path,
        ],
    )
    yag.close()


class SendLogApplication(PrivateMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("发送日志应用", "发送日志应用", False)
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: PrivateMesssageInfo) -> None:
        # 在这里实现发送日志的逻辑
        send_log_email()
        await SayPrivte(message.websocket, message.senderId, "发送日志成功喵！")

    def judge(self, message: PrivateMesssageInfo) -> bool:
        """判断是否触发应用"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可"), "日志"]
        ) and message.senderId in load_setting("developers_list", [])


# Notice应用
from data.application.notice_application import NoticeMessageApplication
from data.message.notice_message_info import NoticeMessageInfo
from data.enumerates import NoticeType


# 拍一拍卖萌应用
class PokeCuteApplication(NoticeMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("拍一拍卖萌应用", "拍一拍卖萌应用", False)
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: NoticeMessageInfo) -> None:
        list = ["res/cute3.gif", "res/cute4.gif", "res/cute5.gif", "res/cute6.gif"]
        path = random.choice(list)
        with open(path, "rb") as image_file:
            image_data = image_file.read()
        image_base64 = base64.b64encode(image_data)
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": message.groupId,
                "message": [
                    {
                        "type": "image",
                        "data": {"file": "base64://" + image_base64.decode("utf-8")},
                    },
                ],
            },
        }
        await message.websocket.send(json.dumps(payload))

    def judge(self, message: NoticeMessageInfo) -> bool:
        """判断是否触发应用"""
        return (
            message.noticeEventType == NoticeType.GROUP_POKE
            and message.target_id == load_setting("bot_id", message.botId)
        )


from function.group_setting import LoadGroupSetting, DumpGroupSetting


# 有人离开应用
class GroupMemberDecreaseApplication(NoticeMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("离开欢送应用", "离开欢送应用", False)
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: NoticeMessageInfo) -> None:
        sender_name = get_user_name(message.senderId, message.groupId)
        group_name = GetGroupName(message.groupId)
        # add_unwelcome(user_id, message["time"], group_id)
        text = [
            "十个小兵人，外出去吃饭；\n一个被呛死，还剩九个人。\n九个小兵人，熬夜熬得深；\n一个睡过头，还剩八个人。\n八个小兵人，动身去德文；\n一个要留下，还剩七个人。\n七个小兵人，一起去砍柴；\n一个砍自己，还剩六个人。\n六个小兵人，无聊玩蜂箱；\n一个被蛰死，还剩五个人。\n五个小兵人，喜欢学法律；\n一个当法官，还剩四个人。\n四个小兵人，下海去逞能；\n一个葬鱼腹，还剩三个人。\n三个小兵人，进了动物园；\n一个遭熊袭，还剩两个人。\n两个小兵人，外出晒太阳；\n一个被晒焦，还剩一个人。\n这个小兵人，孤单又影只；\n投缳上了吊，一个也没剩。",
            "天要下雨，娘要嫁人，由他去吧。",
            "祝他成功。",
        ]
        await SayGroup(
            message.websocket,
            message.groupId,
            "{}({})离开了群{}({})。\n{}".format(
                sender_name,
                message.senderId,
                group_name,
                message.groupId,
                random.choice(text),
            ),
        )
        logging.info(
            f"{sender_name}({message.senderId})离开了群{group_name}({message.groupId})"
        )

    def judge(self, message: NoticeMessageInfo) -> bool:
        """判断是否触发应用"""
        return (
            message.noticeEventType == NoticeType.GROUP_MEMBER_DELETE
            and LoadGroupSetting("group_decrease_reminder", message.groupId, False)
        )


# 随机卖萌应用
from function.database_group import GetAllGroupId


class RandomCuteApplication(MetaMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("随机卖萌", "随机卖萌", False)
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: MetaMessageInfo):
        """处理元消息"""
        list = ["res/cute3.gif", "res/cute4.gif", "res/cute5.gif", "res/cute6.gif"]
        path = random.choice(list)
        with open(path, "rb") as image_file:
            image_data = image_file.read()
        image_base64 = base64.b64encode(image_data)
        groupId = random.choice(GetAllGroupId())
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": groupId,
                "message": [
                    {
                        "type": "image",
                        "data": {"file": "base64://" + image_base64.decode("utf-8")},
                    },
                ],
            },
        }
        await message.websocket.send(json.dumps(payload))

    def judge(self, message: MetaMessageInfo) -> bool:
        """判断是否触发应用"""
        return (
            message.metaEventType == MetaEventType.HEART_BEAT
            and random.random()
            < 0.0001 / 60  # 每次心跳有0.01%的概率触发;心跳:60s/times->1s/times
        )


from function.say import SayImage


# 人呢呢了应用
# 检测到此关键词发送人呢呢了精神图片
class IWantPeopleApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo(
            "人呢呢了/傻子问题应用", "人呢呢了/傻子问题应用"
        )
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        await SayImage(
            message.websocket,
            message.groupId,
            "res/renrenle.jpg",
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return HasKeyWords(message.plainTextMessage, ["人呢呢", "傻子问题"])


# 帮你必应应用
# 当检测到**是啥的时候,自动发送**的必应搜索链接
class BingSearchApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("必应搜索应用", "必应搜索应用")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        search_term = re.search(r"\s*(.+?)是(?:啥|什么)", message.plainTextMessage)
        if search_term:
            query = search_term.group(1).strip()
            # 确保搜索词不为空且长度合理
            if query and len(query) >= 1:
                # 使用urllib.parse.quote将文本转换为UTF-8 URL编码形式
                import urllib.parse

                encoded_query = urllib.parse.quote(query, safe="")
                url = f"https://www.bing.com/search?q={encoded_query}"
                await ReplySay(
                    message.websocket,
                    message.groupId,
                    message.messageId,
                    f"这是关于{query}的必应搜索结果喵,请看一看喵: {url}",
                )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        # 使用更精确的正则表达式确保有实际搜索内容
        pattern = r"(.+?)是(?:啥|什么)"
        return bool(re.search(pattern, message.plainTextMessage)) and get_config(
            "bing_search", message.groupId
        )
