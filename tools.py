import datetime
import time
import base64
import json


def get_now_week() -> int:
    return int(time.strftime("%W"))


def get_timestamp_week(timestamp) -> int:
    return int(datetime.datetime.fromtimestamp(timestamp).strftime("%W"))


def load_setting():
    with open("setting.json", "r") as file:
        setting = json.load(file)
    return setting


def dump_setting(setting: dict):
    with open("setting.json", "w", encoding="utf-8") as f:
        json.dump(setting, f, ensure_ascii=False, indent=4)


def red_qq_avatar():
    return set_qq_avatar("res/leike_red.jpg")


def nomoral_qq_avatar():
    return set_qq_avatar("res/leike.jpg")


def set_qq_avatar(file_dir: str):
    payload = {
        "action": "set_qq_avatar",
        "params": {"file": "base64://" + open_img_by_base64(file_dir).decode("utf-8")},
    }
    return payload


def open_img_by_base64(path: str):
    with open(path, "rb") as image_file:
        image_data = image_file.read()
    return base64.b64encode(image_data)


# red_qq_avatar()
# setting = load_setting()
# print(setting)
