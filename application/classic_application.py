import base64
from datetime import datetime
import json
import logging
import random
import sqlite3
import time

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
        return "签到" in message.painTextMessage


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
        if time.time() - load_setting()["last_update_time"] > 300:
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
                if group["group_id"] not in load_setting()["group_list"]:
                    _setting = load_setting()
                    _setting["group_list"].append(group["group_id"])
                    dump_setting(_setting)
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

                _setting = load_setting()
                _setting["last_update_time"] = time.time()
                dump_setting(_setting)
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
from tools.tools import HasKeyWords
from function.datebase_user import IsDeveloper


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
        raw_message = message.painTextMessage
        user_id = message.senderId
        group_id = message.groupId
        websocket = message.websocket
        for at_id in message.atList:
            if HasKeyWords(raw_message, ["你是GAY", "你是gay"]) and IsAdmin(
                user_id, group_id
            ):
                if at_id not in load_setting()["boring"]:
                    _setting = load_setting()
                    _setting["boring"].append(at_id)
                    dump_setting(_setting)
                    await SayGroup(
                        websocket,
                        group_id,
                        f"{get_user_name(at_id, group_id)},GAY追杀令喵!!!!",
                    )
            elif HasKeyWords(raw_message, ["你不是GAY", "你不是gay"]) and IsAdmin(
                user_id, group_id
            ):
                _setting = load_setting()
                while at_id in load_setting()["boring"]:
                    _setting["boring"].remove(at_id)
                dump_setting(_setting)
                await SayGroup(
                    websocket,
                    group_id,
                    f"{get_user_name(at_id, group_id)},GAY追杀令取消了喵。",
                )
            elif HasKeyWords(raw_message, ["不要哈气"]) and IsAdmin(user_id, group_id):
                _setting = load_setting()
                while at_id in load_setting()["huffing"]:
                    _setting["huffing"].remove(at_id)
                dump_setting(_setting)
                await SayGroup(
                    websocket,
                    group_id,
                    f"{get_user_name(at_id, group_id)},乐可停止追杀你了喵！",
                )
            elif HasKeyWords(raw_message, ["哈气"]) and IsAdmin(user_id, group_id):
                _setting = load_setting()
                if at_id not in load_setting()["huffing"]:
                    _setting["huffing"].append(at_id)
                    dump_setting(_setting)
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
                _setting = load_setting()
                if at_id not in load_setting()["fly"]:
                    _setting["fly"].append(at_id)
                    dump_setting(_setting)
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
                while at_id in load_setting()["fly"]:
                    _setting["fly"].remove(at_id)
                dump_setting(_setting)
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
                    load_setting()["defense_times"],
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
        if user_id in load_setting()["boring"]:
            await BoringReply(websocket, user_id, group_id, message_id)
        if user_id in load_setting()["huffing"]:
            await HuffingReplay(websocket, user_id, group_id, message_id)
        if user_id in load_setting()["fly"]:
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
