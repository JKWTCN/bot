import base64
import logging
import requests
import json

from Class.Group_member import get_user_name
from bot_database import change_point, find_point


# 乐可有概率卖萌
async def cute(websocket, group_id: int):
    path = "res/cute.gif"
    logging.info("乐可卖萌")
    with open(path, "rb") as image_file:
        image_data = image_file.read()
    image_base64 = base64.b64encode(image_data)
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": {
                "type": "image",
                "data": {"file": "base64://" + image_base64.decode("utf-8")},
            },
        },
    }
    await websocket.send(json.dumps(payload))


# 发送一张绝对涩的涩图
async def sex_img(websocket, user_id: int, group_id: int):
    now_point = find_point(user_id)
    if now_point < 500000:
        payload = {
            "action": "send_msg",
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
            "action": "send_msg",
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


# kfcv我50彩蛋
async def kfc_v_me_50(websocket, group_id: int):
    r = requests.get("https://api.shadiao.pro/kfc")
    data = json.loads(r.text)
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "text", "data": {"text": data["data"]["text"]}},
            ],
        },
    }
    await websocket.send(json.dumps(payload))
