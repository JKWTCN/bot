import datetime
import logging
import string
import time
import base64
import json
import traceback

from matplotlib.font_manager import fontManager


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


# 时间戳转日期字符串
def timestamp_to_date(timestamp: int):
    return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


# 获取到现在离明天6点的秒数
def GetSleepSeconds():
    now = datetime.datetime.now()
    today_begin = datetime.datetime(now.year, now.month, now.day, 6, 0, 0)
    tomorrow_begin = today_begin + datetime.timedelta(days=1)
    rest_seconds = (tomorrow_begin - now).seconds
    return rest_seconds


# 要求全部在
def HasAllKeyWords(text: str, key_words: list) -> bool:
    lower_string_list = [s.lower() for s in key_words]

    for key_word in lower_string_list:
        if key_word not in text.lower():
            return False
    return True


# 要求全部不在
def HasNoneKeyWords(text: str, key_words: list) -> bool:
    lower_string_list = [s.lower() for s in key_words]
    for key_word in lower_string_list:
        if key_word in text.lower():
            return False
    return True


# 有一个关键词即可
def HasKeyWords(text: str, key_words: list) -> bool:
    lower_string_list = [s.lower() for s in key_words]
    for key_word in lower_string_list:
        if key_word in text.lower():
            return True
    return False


# 有一个关键词不在即可
def HasNoOneKeyWords(text: str, key_words: list) -> bool:
    lower_string_list = [s.lower() for s in key_words]
    for key_word in lower_string_list:
        if key_word not in text.lower():
            return True
    return False


# 判断是否有Bot名字
def HasBotName(text: str) -> bool:
    bot_name = load_setting("bot_name", "乐可")
    if bot_name in text:
        return True
    else:
        return False


async def say_and_echo(websocket, group_id: int, text: str, echo: str):
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": text,
        },
        "echo": echo,
    }
    await websocket.send(json.dumps(payload))


# 是否包含中文字符
def HasChinese(text: str) -> bool:
    import re

    res = re.findall(r"([\u4e00-\u9fa5]+)", text)
    if len(res) != 0:
        return True
    else:
        res = re.findall(r"([\u3400-\u4db5]+)", text)
        if len(res) != 0:
            return True
        else:
            return False


# 寻找数字
def FindNum(text: str):
    import re

    # 首先尝试匹配负数或正数
    result = re.search(r"-?\d+", text)
    if result != None:
        num = int(result.group())
        return num

    # 如果没有找到阿拉伯数字，尝试匹配中文数字
    chinese_num_dict = {
        "零": 0,
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
        "十一": 11,
        "十二": 12,
        "十三": 13,
        "十四": 14,
        "十五": 15,
        "十六": 16,
        "十七": 17,
        "十八": 18,
        "十九": 19,
        "二十": 20,
        "二十一": 21,
        "二十二": 22,
        "二十三": 23,
        "二十四": 24,
        "二十五": 25,
        "二十六": 26,
        "二十七": 27,
        "二十八": 28,
        "二十九": 29,
        "三十": 30,
        "三十一": 31,
        "三十二": 32,
        "三十三": 33,
        "三十四": 34,
        "三十五": 35,
        "三十六": 36,
        "三十七": 37,
        "三十八": 38,
        "三十九": 39,
        "四十": 40,
        "四十一": 41,
        "四十二": 42,
        "四十三": 43,
        "四十四": 44,
        "四十五": 45,
        "四十六": 46,
        "四十七": 47,
        "四十八": 48,
        "四十九": 49,
        "五十": 50,
        "五十一": 51,
        "五十二": 52,
        "五十三": 53,
        "五十四": 54,
        "五十五": 55,
        "五十六": 56,
        "五十七": 57,
        "五十八": 58,
        "五十九": 59,
        "六十": 60,
        "六十一": 61,
        "六十二": 62,
        "六十三": 63,
        "六十四": 64,
        "六十五": 65,
        "六十六": 66,
        "六十七": 67,
        "六十八": 68,
        "六十九": 69,
        "七十": 70,
        "七十一": 71,
        "七十二": 72,
        "七十三": 73,
        "七十四": 74,
        "七十五": 75,
        "七十六": 76,
        "七十七": 77,
        "七十八": 78,
        "七十九": 79,
        "八十": 80,
        "八十一": 81,
        "八十二": 82,
        "八十三": 83,
        "八十四": 84,
        "八十五": 85,
        "八十六": 86,
        "八十七": 87,
        "八十八": 88,
        "八十九": 89,
        "九十": 90,
        "九十一": 91,
        "九十二": 92,
        "九十三": 93,
        "九十四": 94,
        "九十五": 95,
        "九十六": 96,
        "九十七": 97,
        "九十八": 98,
        "九十九": 99,
        "一百": 100,
    }

    # 按长度从长到短排序，优先匹配更长的中文数字
    for chinese_num in sorted(
        chinese_num_dict.keys(), key=lambda x: len(x), reverse=True
    ):
        if chinese_num in text:
            return chinese_num_dict[chinese_num]

    # 如果没有找到任何数字，返回-1
    return -1


# 获取系统状态
def ShowSystemInfoTableByBase64():
    import matplotlib.pyplot as plt
    from plottable import Table
    import pandas as pd
    import base64
    import psutil
    import platform

    plt.rcParams["font.sans-serif"] = load_static_setting("font", ["Unifont"])
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


async def GetSystemInfoTable(websocket, group_id: int):
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
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
    await websocket.send(json.dumps(payload))


def getTemper():
    """
    获取内置温度传感器温度
    cpu温度,cpu温度墙,gpu温度
    """
    import re
    import subprocess

    command = "sensors"
    result = subprocess.check_output(command, shell=True, text=True)
    pattern = r"\d+\.\d+"
    matches = re.findall(pattern, str(result))
    return float(matches[0]), float(matches[1]), float(matches[2])


def GetNowHour() -> int:
    return int(time.strftime("%H"))


def GetNowMinute() -> int:
    return int(time.strftime("%M"))


def get_now_week() -> int:
    return int(time.strftime("%W"))


def GetLogTime() -> int:
    return int(time.strftime("%Y%m%d"))


def GetNowDay() -> int:
    """获取当前日期的天数"""
    return int(time.strftime("%Y%m%d"))


def GetNowMonth() -> int:
    return int(time.strftime("%m"))


def get_timestamp_week(timestamp) -> int:
    return int(datetime.datetime.fromtimestamp(timestamp).strftime("%W"))


def check_all_miao(text):
    """
    检查给定文本中的字符除标点符号外的字符是否都是"喵"
    """
    # 遍历文本中的每个字符
    # 获取所有标点符号
    punctuations = string.punctuation + "。，、；：「」『』（）【】《》？！…—"

    for char in text:
        # 如果字符不是标点符号且不是"喵"，返回False
        if char not in punctuations and char != "喵":
            return False
    # 所有非标点符号字符都是"喵"
    return True


settingLock = False


def load_static_setting(setting_name: str, default_value):
    # reading the static settings, e.g. meme_path and developers_list
    try:
        with open("static_setting.json", "r", encoding="utf-8") as file:
            setting = json.load(file)
        return setting[setting_name]
    except Exception as e:
        logging.error(f"读取静态配置文件出错: {e},{traceback.format_exc()}")
        return default_value


def load_setting(setting_name: str, default_value):
    # reading the static settings, e.g. meme_path and developers_list
    if setting_name in [
        "meme_path",
        "developers_list",
        "daily_point_limit",
        "tushare_token",
        "bot_name",
        "bot_id",
    ]:
        try:
            with open("static_setting.json", "r", encoding="utf-8") as file:
                setting = json.load(file)
            return setting[setting_name]
        except Exception as e:
            logging.error(f"读取静态配置文件出错: {e},{traceback.format_exc()}")
            return default_value
    # reading the dynamic settings, e.g. bot_name and debug_mode
    global settingLock
    while settingLock:
        time.sleep(0.001)
    settingLock = True
    try:
        with open("setting.json", "r", encoding="utf-8") as file:
            setting = json.load(file)
        settingLock = False
        return setting[setting_name]
    except Exception as e:
        if e.args[0] == "Expecting value: line 1 column 1 (char 0)":
            logging.error(f"配置文件为空,重建新配置文件;")
        elif type(e) == KeyError:
            logging.error(f"{setting_name},键值缺失,补全默认值{default_value}")
        else:
            logging.error(f"读取配置文件出错: {e},{traceback.format_exc()}")
    settingLock = False
    dump_setting(setting_name, default_value)
    return default_value


def dump_setting(setting_name: str, value):
    global settingLock
    while settingLock:
        time.sleep(0.001)
    settingLock = True
    try:
        with open("setting.json", "r", encoding="utf-8") as file:
            setting = json.load(file)
    except Exception as e:
        logging.error(f"读取配置文件出错,清空配置文件: {e},{traceback.format_exc()}")
        setting = {}
    setting[setting_name] = value
    with open("setting.json", "w", encoding="utf-8") as f:
        json.dump(setting, f, ensure_ascii=False, indent=4)
    settingLock = False


async def red_qq_avatar(websocket):
    await set_qq_avatar(websocket, "res/leike_red.jpg")


async def nomoral_qq_avatar(
    websocket,
):
    await set_qq_avatar(websocket, "res/leike.jpg")


async def set_qq_avatar(websocket, file_dir: str):
    payload = {
        "action": "set_qq_avatar",
        "params": {"file": "base64://" + open_img_by_base64(file_dir).decode("utf-8")},
    }
    await websocket.send(json.dumps(payload))


def open_img_by_base64(path: str):
    with open(path, "rb") as image_file:
        image_data = image_file.read()
    return base64.b64encode(image_data)


def IsSameDay(t1, t2, tz_count=28800):
    if int((int(t1) + int(tz_count)) / 86400) == int((int(t2) + int(tz_count)) / 86400):
        return True
    else:
        return False


def IsToday(t1, tz_count=28800):
    """
    判断时间戳t1是否是今天
    :param t1: 时间戳
    :param tz_count: 时区偏移量，默认值为28800（8小时）
    :return: 如果t1是今天，返回True，否则返回False
    """
    today = datetime.datetime.now().date()
    t1_date = datetime.datetime.fromtimestamp(t1).date()
    return today == t1_date


def is_today(t1, t2, tz_count=28800):
    if int((int(t1) + int(tz_count)) / 86400) == int((int(t2) + int(tz_count)) / 86400):
        return True
    else:
        return False


def get_now_time_emoji():
    month_emoji = "㋀㋁㋂㋃㋄㋅㋆㋇㋈㋉㋊㋋"
    day_emoji = "㏠㏡㏢㏣㏤㏥㏦㏧㏨㏩㏪㏫㏬㏭㏮㏯㏰㏱㏲㏳㏴㏵㏶㏷㏸㏹㏺㏻㏼㏽㏾"
    chock_emjoi = "㍙㍚㍛㍜㍝㍞㍟㍠㍡㍢㍣㍤㍥㍦㍧㍨㍩㍪㍫㍬㍭㍮㍯㍰㍘"


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


def GetNCWCPort():
    """
    获取NapCat WClient端口
    """
    return load_setting("napcat_wclient_port", 27431)


def GetNCHSPort():
    """
    获取NapCat HServer端口
    """
    return load_setting("napcat_hserver_port", 27433)


def GetOllamaPort():
    """
    获取Ollama端口
    """
    return load_setting("ollama_port", 11434)


def find_fonts():
    all_fonts = [f.name for f in fontManager.ttflist]
    return all_fonts
