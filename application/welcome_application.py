import base64
import json
import os
import random
import sqlite3
import string
from data.application.notice_application import (
    NoticeMessageApplication,
    NoticeMessageInfo,
)
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType, MetaEventType, NoticeType
from function.say import ReplySay
import logging
from function.datebase_user import BotIsAdmin
from tools.tools import load_setting,get_user_level,get_person_name
from function.GroupConfig import get_config
from captcha.image import ImageCaptcha


async def welcome_new(websocket, user_id: int, group_id: int):
    """欢迎新成员入群"""
    with open("res/welcome.jpg", "rb") as image_file:
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
                        "text": "\n欢迎入群喵!愿原力与你同在！\n请花一分钟时间阅读以下群规\n1.三次元涩涩请合并转发后发群里,不能直接发！！！否则禁言惩罚。\n2.还没有想好。\n3.搬史记着补涩图。\n4.乐可每天都会检查群友的喵，两个月未活跃的群友会被乐可请出的喵。\n5.人家叫乐可，不要记错了喵！\n6.每月25日是本群的喵喵日，那天说话记得带喵，否则乐可会禁言你的喵。"
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


async def welcom_new_no_admin(websocket, user_id: int, group_id: int):
    with open("res/welcome.jpg", "rb") as image_file:
        image_data = image_file.read()
    image_base64 = base64.b64encode(image_data)
    if get_config("cat_day_date", group_id) != -1:
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": [
                    {"type": "at", "data": {"qq": user_id}},
                    {
                        "type": "text",
                        "data": {
                            "text": f"\n欢迎入群喵!每月{get_config("cat_day_date", group_id)}日是本群的喵喵日，那天说话记得带喵，否则乐可会禁言你的喵。愿原力与你同在！"
                        },
                    },
                    {
                        "type": "image",
                        "data": {"file": "base64://" + image_base64.decode("utf-8")},
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
                    {
                        "type": "text",
                        "data": {"text": "\n欢迎入群喵!愿原力与你同在！"},
                    },
                    {
                        "type": "image",
                        "data": {"file": "base64://" + image_base64.decode("utf-8")},
                    },
                ],
            },
        }
    await websocket.send(json.dumps(payload))


# 以下的验证应用
# 创建验证码并写入数据库
def create_vcode(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    chr_all = string.ascii_uppercase + string.digits
    chr_4 = "".join(random.sample(chr_all, 4))
    image = ImageCaptcha().generate_image(chr_4)
    if not os.path.exists("vcode"):
        os.makedirs("vcode")
    image.save("vcode/{}_{}.jpg".format(user_id, group_id))
    cur.execute(
        "INSERT INTO vcode VALUES(?,?,?,?,?)",
        (
            user_id,
            group_id,
            chr_4,
            5,
            time.time(),
        ),
    )
    conn.commit()
    conn.close()
    return chr_4


# 更新验证码
def update_vcode(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    chr_all = string.ascii_uppercase + string.digits
    chr_4 = "".join(random.sample(chr_all, 4))
    image = ImageCaptcha().generate_image(chr_4)
    image.save("./vcode/{}_{}.jpg".format(user_id, group_id))
    cur.execute(
        "UPDATE vcode SET text=?,times=?,time=? where user_id=? and group_id=?",
        (
            chr_4,
            5,
            time.time(),
            user_id,
            group_id,
        ),
    )
    conn.commit()
    conn.close()
    return chr_4


# 根据user_id和group_id查找验证码
def find_vcode(user_id: int, group_id: int) -> tuple[bool, str]:
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    cur.execute(
        "SELECT text FROM vcode where user_id=? and group_id=?", (user_id, group_id)
    )
    data = cur.fetchall()
    if len(data) == 0:
        return (False, "-1")
    else:
        return (True, data[0][0])


# 删除验证码
def delete_vcode(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    cur.execute("delete FROM vcode where user_id=? and group_id=?", (user_id, group_id))
    conn.commit()
    conn.close()
    os.remove("./vcode/{}_{}.jpg".format(user_id, group_id))


# 查找最后一次验证时间
def find_last_time(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    cur.execute(
        "SELECT time FROM vcode where user_id=? and group_id=?", (user_id, group_id)
    )
    data = cur.fetchall()
    # print(cur.fetchall())
    if len(data) == 0:
        return -1
    return data[0][0]


# 更新最后一次的验证时间
def updata_last_time(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    cur.execute(
        "UPDATE vcode SET time=? where user_id=? and group_id=?",
        (
            time.time(),
            user_id,
            group_id,
        ),
    )
    conn.commit()
    conn.close()


# 查找所有
def find_all(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM vcode where user_id=? and group_id=?",
        (
            user_id,
            group_id,
        ),
    )
    return (
        cur.fetchall()[0][0],
        cur.fetchall()[0][1],
        cur.fetchall()[0][2],
        cur.fetchall()[0][3],
        cur.fetchall()[0][4],
    )


# 查找验证次数
def find_times(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    cur.execute(
        "SELECT times FROM vcode where user_id=? and group_id=?", (user_id, group_id)
    )
    return cur.fetchall()[0][0]


# 更新验证次数
def update_times(user_id: int, group_id: int, times: int):
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    cur.execute(
        "UPDATE vcode SET time=?,times=? where user_id=? and group_id=?",
        (
            time.time(),
            times,
            user_id,
            group_id,
        ),
    )
    conn.commit()
    conn.close()


# 验证 返回(验证结果，剩余验证次数)
def verify(user_id: int, group_id: int, text: str):
    (mod, vcode_str) = find_vcode(user_id, group_id)
    logging.info(
        "{}在{}群里验证,发送{},实际{}".format(user_id, group_id, text, vcode_str)
    )
    if not mod:
        return (False, -1)
    else:
        times = find_times(user_id, group_id)
        times = times - 1
        if vcode_str in text:  # type: ignore
            delete_vcode(user_id, group_id)
            return (True, times)
        else:
            if times <= 0:
                delete_vcode(user_id, group_id)
                return (False, 0)
            else:
                update_times(user_id, group_id, times)
                return (False, times)


# 没有验证成功的说辞
async def verify_fail_say(websocket, user_id: int, group_id: int, times: int):
    with open("./vcode/{}_{}.jpg".format(user_id, group_id), "rb") as image_file:
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
                        "text": f' 验证码输入错误，你还有{times}次机会喵。如果看不清记得说"乐可，看不清"喵。你的验证码如下:'
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


# 验证的说辞
async def welcome_verify(websocket, user_id: int, group_id: int):
    (mod, times) = find_vcode(user_id, group_id)
    if not mod:
        create_vcode(user_id, group_id)
    with open("./vcode/{}_{}.jpg".format(user_id, group_id), "rb") as image_file:
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
                        "text": '\n请在{}分钟内输入以下验证码喵,注意是全大写字符喵。你有5次输入机会喵,如果看不清说"乐可，看不清",乐可会给你换一张验证码的喵。'.format(
                            load_setting("timeout", 5)
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


import time


# 检测是否验证超时
def check_validation_timeout(user_id: int, group_id: int):

    if (
        time.time() - find_last_time(user_id, group_id)
        > load_setting("timeout", 5) * 60
    ):
        return True
    else:
        return False


class WelcomeApplication(NoticeMessageApplication):

    def __init__(
        self,
    ):
        applicationInfo = ApplicationInfo("欢迎和入群验证", "欢迎和入群验证")
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: NoticeMessageInfo):
        level=get_user_level(message.senderId)
        if get_config("level_limit", message.groupId)!=-1 and level<=get_config("level_limit", message.groupId) and level!=-1:
            if(BotIsAdmin(message.groupId)):
                await kick_member(message.websocket,message.senderId,message.groupId)
                await SayGroup(message.websocket,message.groupId,f"用户{get_person_name(message.senderId)}的等级为{level},未达到入群等级限制{get_config('level_limit', message.groupId)},已自动踢出喵！")
            else:
                await SayGroup(message.websocket,message.groupId,f"用户{get_person_name(message.senderId)}的等级为{level},未达到入群等级限制{get_config('level_limit', message.groupId)},可能是广告号,建议管理员手动踢出喵！")
        else:
            if BotIsAdmin(message.groupId):
                await welcome_verify(message.websocket, message.senderId, message.groupId)
            elif message.groupId == load_setting("main_group_id", 0):
                await welcome_new(message.websocket, message.senderId, message.groupId)
            else:
                await welcom_new_no_admin(
                    message.websocket, message.senderId, message.groupId
                )
        
        

    def judge(self, message: NoticeMessageInfo):
        """判断是否触发应用

        Args:
            message (NoticeMessageInfo): 要判断的消息
        """
        # Check if the notice event type is GROUP_MEMBER_ADD
        return message.noticeEventType == NoticeType.GROUP_MEMBER_ADD


from data.application.meta_application import MetaMessageApplication, MetaMessageInfo
from function.datebase_user import BotIsAdmin, IsAdmin, get_user_name
from function.group_operation import ban_new, delete_msg
from function.say import SayGroup
from function.group_operation import kick_member


class RefreshVcodeApplication(MetaMessageApplication):
    """定时刷新验证码应用类
    该类用于定时刷新验证码,并在验证超时后删除验证码.
    该类继承自MetaMessageApplication基类,并实现了处理元消息的抽象方法.
    """

    def __init__(self):
        applicationInfo = ApplicationInfo("刷新验证码", "定时刷新验证码")
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: MetaMessageInfo):
        """处理元消息"""
        for i in os.listdir("./vcode"):
            user_id = int(i.split(".")[0].split("_")[0])
            group_id = int(i.split(".")[0].split("_")[1])
            if check_validation_timeout(
                user_id,
                group_id,
            ):
                sender_name = get_user_name(user_id, group_id)
                if not IsAdmin(user_id, group_id):
                    await ban_new(
                        message.websocket,
                        user_id,
                        group_id,
                        60,
                    )
                    await SayGroup(
                        message.websocket,
                        group_id,
                        f"{sender_name}的验证码已过期，已自动踢出喵！",
                    )
                    await kick_member(message.websocket, user_id, group_id)
                    delete_vcode(user_id, group_id)

    def judge(self, message: MetaMessageInfo) -> bool:
        """判断是否触发应用"""
        # 验证码刷新应该只在心跳事件时触发，避免在连接/断开事件时执行
        return message.metaEventType == MetaEventType.HEART_BEAT


from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo


class VerifyApplication(GroupMessageApplication):
    """验证应用类
    该类用于处理群组中的验证消息
    """

    def __init__(self):
        applicationInfo = ApplicationInfo(
            "入群验证处理", "当为管理员的时候,新群友的入群验证处理"
        )
        super().__init__(applicationInfo, 100, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        """处理验证消息"""
        user_id = message.senderId
        group_id = message.groupId
        websocket = message.websocket
        sender_name = get_user_name(user_id, group_id)
        if "{}_{}.jpg".format(user_id, group_id) in os.listdir("./vcode"):
            if "看不清" in message.plainTextMessage:
                if "{}_{}.jpg".format(user_id, group_id) in os.listdir("./vcode"):
                    update_vcode(user_id, group_id)
                    await welcome_verify(websocket, user_id, group_id)

            else:
                (mod, times) = verify(
                    user_id,
                    group_id,
                    message.plainTextMessage,
                )
                if mod:
                    # 通过验证
                    if group_id == load_setting("admin_group_main", 0):
                        await ban_new(
                            websocket,
                            user_id,
                            group_id,
                            60,
                        )
                        await welcome_new(websocket, user_id, group_id)
                    else:
                        await welcom_new_no_admin(websocket, user_id, group_id)
                elif times > 0:
                    await verify_fail_say(websocket, user_id, group_id, times)

                elif times <= 0:
                    if not IsAdmin(user_id, group_id):
                        await kick_member(websocket, user_id, group_id)
                        await SayGroup(
                            websocket,
                            group_id,
                            "{},验证码输入错误，你没有机会了喵。有缘江湖相会了喵。".format(
                                sender_name
                            ),
                        )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        user_id = message.senderId
        group_id = message.groupId
        return "{}_{}.jpg".format(user_id, group_id) in os.listdir("vcode")


from tools.tools import HasKeyWords

# 导入线程池包装器，避免数据库锁定
from database.sync_wrapper import run_in_thread_sync




class ManualVerifyApplication(GroupMessageApplication):
    """人工通过验证应用类
    该类用于处理群组中的人工通过验证消息
    """

    def __init__(self):
        applicationInfo = ApplicationInfo(
            "人工通过验证", "当为管理员的时候,新群友的人工通过验证"
        )
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        """处理人工通过验证消息"""
        user_id = message.senderId
        group_id = message.groupId
        websocket = message.websocket
        sender_name = get_user_name(user_id, group_id)
        if HasKeyWords(message.plainTextMessage, ["通过验证", "验证通过"]):
            for at_id in message.atList:
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
                            if group_id == load_setting("main_group_id", 0):
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
        user_id = message.senderId
        group_id = message.groupId
        for user_id in message.atList:
            if "{}_{}.jpg".format(user_id, group_id) in os.listdir("./vcode"):
                return True
        return False
