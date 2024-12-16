import base64
from captcha.image import ImageCaptcha
import random
import string
import sqlite3
import time
import os
import logging
import json

from Class.Group_member import get_user_name


# 创建验证码并写入数据库
def create_vcode(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    chr_all = string.ascii_uppercase + string.digits
    chr_4 = "".join(random.sample(chr_all, 4))
    image = ImageCaptcha().generate_image(chr_4)
    image.save("./vcode/{}_{}.jpg".format(user_id, group_id))
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
    conn.close()
    return chr_4


# 更新验证码
def update_vcode(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
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
    conn.close()
    return chr_4


# 根据user_id和group_id查找验证码
def find_vcode(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT text FROM vcode where user_id=? and group_id=?", (user_id, group_id)
    )
    data = cur.fetchall()
    if len(data) == 0:
        return (False, -1)
    else:
        return (True, data[0][0])


# 删除验证码
def delete_vcode(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("delete FROM vcode where user_id=? and group_id=?", (user_id, group_id))
    conn.commit()
conn.close()
    os.remove("./vcode/{}_{}.jpg".format(user_id, group_id))


# 查找最后一次验证时间
def find_last_time(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
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
    conn = sqlite3.connect("bot.db")
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
    conn = sqlite3.connect("bot.db")
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
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT times FROM vcode where user_id=? and group_id=?", (user_id, group_id)
    )
    return cur.fetchall()[0][0]


# 更新验证次数
def update_times(user_id: int, group_id: int, times: int):
    conn = sqlite3.connect("bot.db")
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
        if vcode_str in text:
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
    from tools import load_setting

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
    from tools import load_setting

    setting = load_setting()
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
                            setting["timeout"]
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


# 检测是否验证超时
def check_validation_timeout(user_id: int, group_id: int):
    from tools import load_setting

    setting = load_setting()
    if time.time() - find_last_time(user_id, group_id) > setting["timeout"] * 60:
        return True
    else:
        return False


# print(welcome_verify(1, 123))
# update_vcode(1,123)
# print(verify(1, 123, "Sc0Ta"))

# print(os.listdir("./vcode"))
# for i in os.listdir("./vcode"):
#     print(i)
#     print(i.split(".")[0])
# for i in os.listdir("./vcode"):
#     print(i.split(".")[0].split("_")[0])
#     if check_validation_timeout(i.split(".")[0].split("_")[0],i.split(".")[0].split("_")[1]):
#         print("True")
