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


def is_today(t1, t2, tz_count=28800):
    if int((int(t1) + int(tz_count)) / 86400) == int((int(t2) + int(tz_count)) / 86400):
        return True
    else:
        return False


def GetFileSize(filePath):
    import os

    fsize = os.path.getsize(filePath)  # 返回的是字节大小
    if fsize < 1024:
        return (round(fsize, 2), "Byte")
    else:
        KBX = fsize / 1024
        if KBX < 1024:
            return (round(KBX, 2), "KB")
        else:
            MBX = KBX / 1024
            if MBX < 1024:
                return (round(MBX, 2), "MB")
            else:
                return (round(MBX / 1024, 2), "GB")


def GetDirSize(path="."):
    import os

    total = 0
    with os.scandir(path) as it:
        for entry in it:
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += GetDirSize(entry.path)
    return total


def GetDirSizeByUnit(path="."):
    fsize = GetDirSize(path)
    if fsize < 1024:
        return (round(fsize, 2), "Byte")
    else:
        KBX = fsize / 1024
        if KBX < 1024:
            return (round(KBX, 2), "KB")
        else:
            MBX = KBX / 1024
            if MBX < 1024:
                return (round(MBX, 2), "MB")
            else:
                return (round(MBX / 1024, 2), "GB")
