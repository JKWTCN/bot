import requests
from random import choice
import json


# 看世界
async def photo_new(websocket, user_id: int, group_id: int):
    r = requests.get("https://api.tangdouz.com/60.php")
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {"type": "image", "data": {"file": r.text}},
            ],
        },
    }
    await websocket.send(json.dumps(payload))


# 日报
async def daily_paper(websocket, user_id: int, group_id: int):
    r = requests.get("https://api.tangdouz.com/a/60/")
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {"type": "image", "data": {"file": r.text}},
            ],
        },
    }
    await websocket.send(json.dumps(payload))


# 悲报
async def SoSad(websocket, group_id: int, text: str):
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {
                    "type": "image",
                    "data": {"file": f"https://www.oexan.cn/API/beibao.php?msg={text}"},
                },
            ],
        },
    }
    await websocket.send(json.dumps(payload))


# 喜报
async def SoHappy(websocket, group_id: int, text: str):
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {
                    "type": "image",
                    "data": {"file": f"https://api.tangdouz.com/wz/xb.php?nr={text}"},
                },
            ],
        },
    }
    await websocket.send(json.dumps(payload))


# 你们看到她了吗
async def SoCute(websocket, user_id: int, group_id: int):
    payload = {
        "action": "send_msg",
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


# 塔罗牌
def get_tarot_cards():
    r = requests.get("https://api.tangdouz.com/tarot.php")
    # print(r.text.split("±"))
    return r.text.split("±")


# 涩涩
async def get_cos(websocket, user_id: int, group_id: int):
    r = requests.get("https://api.tangdouz.com/hlxmt.php")
    text = r.text.split("±")
    text = list(filter(None, text))
    # print(text)
    payload = {
        "action": "send_msg",
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
    r = requests.get("https://api.vvhan.com/api/wallpaper/mobileGirl?type=json")
    json_data = json.loads(r.text)
    if json_data.hasKey("url"):
        payload["params"]["message"].append(
            {"type": "image", "data": {"file": json_data["url"]}},
        )
    payload["params"]["message"].append(
        {"type": "text", "data": {"text": "随机PC分辨率美图\n"}},
    )
    r = requests.get("https://api.vvhan.com/api/wallpaper/pcGirl?type=json")
    json_data = json.loads(r.text)
    if json_data.hasKey("url"):
        payload["params"]["message"].append(
            {"type": "image", "data": {"file": json_data["url"]}},
        )
    await websocket.send(json.dumps(payload))


# 随机一言
async def one_word(websocket, user_id: int, group_id: int):
    url_list = [
        "https://api.tangdouz.com/aqgy.php",
        "https://api.tangdouz.com/sjyy.php",
        "https://api.tangdouz.com/a/one.php",
    ]
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {
                    "type": "text",
                    "data": {
                        "text": "\n{}".format(requests.get(choice(url_list)).text)
                    },
                },
            ],
        },
    }
    await websocket.send(json.dumps(payload))


# 随机三次元图片
async def radom_real(websocket, user_id: int, group_id: int):
    url1 = requests.get("https://api.tangdouz.com/mn.php")
    url2 = requests.get(
        choice(["https://api.tangdouz.com/mt.php", "https://api.tangdouz.com/mt1.php"])
    )
    payload = {
        "action": "send_msg",
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


# 随机二次元图片
async def radom_waifu(websocket, user_id: int, group_id: int):
    r = requests.get("https://api.tangdouz.com/abz/dm.php")
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {"type": "image", "data": {"file": r.text}},
            ],
        },
    }
    await websocket.send(json.dumps(payload))


# 每日一言
async def daily_word(websocket, user_id: int, group_id: int):
    r = requests.get("https://api.tangdouz.com/a/perday.php")
    # print(r.text)
    text = r.text.split("±")
    # print(text)
    payload = {
        "action": "send_msg",
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


# 塔罗牌
async def return_trarot_cards(websocket, user_id: int, group_id: int):
    text = get_tarot_cards()
    payload = {
        "action": "send_msg",
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


# 抽签
async def AnswerBook(websocket, user_id: int, group_id: int):
    r = requests.get("https://api.tangdouz.com/answer.php")
    # print(r.text)
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {
                    "type": "text",
                    "data": {"text": "\n{}".format(r.text)},
                },
            ],
        },
    }
    # print(payload)
    await websocket.send(json.dumps(payload))


# 抽签
async def drawing(websocket, user_id: int, group_id: int):
    r = requests.get("https://api.tangdouz.com/a/ccscq.php")
    # print(r.text)
    payload = {
        "action": "send_msg",
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


# return_trarot_cards()
# get_cos(1, 1)
# drawing(1,1)
