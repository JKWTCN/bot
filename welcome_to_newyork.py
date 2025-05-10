import base64
import json

from tools import load_setting


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


async def ban_new(websocket, user_id: int, group_id: int, duration: int):
    from Class.Group_member import IsAdmin

    if IsAdmin(user_id, group_id):
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": "我，打管理?真的假的?",
            },
        }
        await websocket.send(json.dumps(payload))
    else:
        payload = {
            "action": "set_group_ban",
            "params": {"group_id": group_id, "user_id": user_id, "duration": duration},
        }
        await websocket.send(json.dumps(payload))


async def new_group_vcode(websocket, user_id: int, group_id: int):
    with open("vcode/{}.jpg".format(user_id), "rb") as image_file:
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
                        "text": '验证码已发送，请输入验证码,注意是全大写字符喵。你有三次机会回答喵。如果看不清，请说"乐可，看不清"，乐可会给你换一张验证码喵！'
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


async def welcome_new(websocket, user_id: int, group_id: int):
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


from GroupConfig import get_config, set_config, manage_config


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


async def leave(websocket, user_id: int, group_id: int):
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {
                    "type": "text",
                    "data": {"text": "悲，{}离开了我们大家庭。".format(user_id)},
                },
            ],
        },
    }
    await websocket.send(json.dumps(payload))


async def get_qunyou_message(websocket, user_id: int, group_id: int):
    payload = {
        "action": "get_group_member_info ",
        "params": {"group_id": group_id, "user_id": user_id, "no_cache": True},
    }
    await websocket.send(json.dumps(payload))
