import base64
import logging
import requests
import json


def cute(group_id: int):
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
    return payload



def kfc_v_me_50(group_id: int):
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
    return payload


