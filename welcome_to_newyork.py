import base64

def return_function(user_id: int, group_id: int):
    with open("res/function.png", "rb") as image_file:
        image_data = image_file.read()
    image_base64 = base64.b64encode(image_data)
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {
                    "type": "image",
                    "data": {"file": "base64://" + image_base64.decode("utf-8")},
                },
            ],
        },
    }
    return payload


def ban_new(user_id: int, group_id: int, duration: int):
    payload = {
        "action": "set_group_ban",
        "params": {"group_id": group_id, "user_id": user_id, "duration": duration},
    }
    return payload

def new_group_vcode(user_id: int, group_id: int):
    with open("vcode/{}.jpg".format(user_id), "rb") as image_file:
        image_data = image_file.read()
    image_base64 = base64.b64encode(image_data)
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {
                    "type": "text",
                    "data": {
                        "text": "验证码已发送，请输入验证码。你有三次机会回答喵。如果看不清，请说<乐可，看不清>，乐可会给你换一张验证码喵！"
                    },
                },
                {
                    "type": "image",
                    "data": {"file": "base64://" + image_base64.decode("utf-8")},
                },
            ],
        },
    }
    return payload

def welcome_new(user_id: int, group_id: int):
    with open("res/welcome.jpg", "rb") as image_file:
        image_data = image_file.read()
    image_base64 = base64.b64encode(image_data)
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {
                    "type": "text",
                    "data": {
                        "text": "\n欢迎入群喵!愿原力与你同在！\n请花一分钟时间阅读以下群规\n1.三次元涩涩请合并转发后发群里,不能直接发！！！否则禁言惩罚。\n2.还没有想好。\n3.搬史记着补涩图。\n4.乐可每天都会检查群友的喵，三个月无活跃或两个月未活跃且从未活跃过的群友会被乐可请出的喵。\n5.人家叫乐可，不要记错了喵！\n6.每月25日是本群的喵喵日，那天说话记得带喵，否则乐可会禁言你的喵。"
                    },
                },
                {
                    "type": "image",
                    "data": {"file": "base64://" + image_base64.decode("utf-8")},
                },
            ],
        },
    }
    return payload


def welcom_new_no_admin(user_id: int, group_id: int):
    with open("res/welcome.jpg", "rb") as image_file:
        image_data = image_file.read()
    image_base64 = base64.b64encode(image_data)
    payload = {
        "action": "send_msg",
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
    return payload


def leave(user_id: int, group_id: int):
    payload = {
        "action": "send_msg",
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
    return payload


def get_qunyou_message(user_id: int, group_id: int):
    payload = {
        "action": "get_group_member_info ",
        "params": {"group_id": group_id, "user_id": user_id},
    }
    return payload
