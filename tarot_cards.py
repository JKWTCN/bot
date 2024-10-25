import requests
from random import choice


# 看世界
def photo_new(user_id: int, group_id: int):
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
    return payload


# 日报
def daily_paper(user_id: int, group_id: int):
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
    return payload


# 塔罗牌
def get_tarot_cards():
    r = requests.get("https://api.tangdouz.com/tarot.php")
    # print(r.text.split("±"))
    return r.text.split("±")


# 涩涩
def get_cos(user_id: int, group_id: int):
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
    return payload


# 随机一言
def one_word(user_id: int, group_id: int):
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
    return payload


# 随机三次元图片
def radom_real(user_id: int, group_id: int):
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
    return payload


# 随机二次元图片
def radom_waifu(user_id: int, group_id: int):
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
    return payload


# 每日一言
def daily_word(user_id: int, group_id: int):
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
    return payload


# 塔罗牌
def return_trarot_cards(user_id: int, group_id: int):
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
    return payload


# 抽签
def drawing(user_id: int, group_id: int):
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
    return payload


# return_trarot_cards()
# get_cos(1, 1)
# drawing(1,1)
