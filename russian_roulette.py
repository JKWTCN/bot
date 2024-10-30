import random
import bot_database


# @return (x,y)
# x=-1代表子弹错误 y=-1代表积分数目错误
# x=-2,y=-2代表赌上全部
# 装弹 <子弹数> <积分数>
def pro_str(message: str):
    if message.endswith((".", "。")):
        message = message[:-1]
    parm_list_str = message.split(" ")
    # print(parm_list_str)
    # 只输入了子弹，未输入积分
    if len(parm_list_str) == 2:
        if (int(parm_list_str[1])) > 0 and int(parm_list_str[1]) <= 5:
            return (parm_list_str[1], -2)
        else:
            return (-1, -2)
    # 只输入了装弹
    elif len(parm_list_str) == 1:
        return (-2, -2)
    else:
        if int(parm_list_str[2]) <= 0:
            y = -1
        else:
            y = parm_list_str[2]
        if int(parm_list_str[1]) <= 0 or int(parm_list_str[1]) > 5:
            x = -1
        else:
            x = parm_list_str[1]
        return (x, y)


def russian_pve_shot(user_id: int, group_id: int,nick_name:str):
    now_shots = bot_database.check_russian_pve(user_id)
    if now_shots == -1:
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": [
                    {"type": "at", "data": {"qq": user_id}},
                    {
                        "type": "text",
                        "data": {"text": "\n拔枪吧！午时已到！乐可可是第一神枪手喵！"},
                    },
                ],
            },
        }
        return payload
    now_choice = random.randint(1, now_shots)
    # 自己开枪中枪了
    if now_choice == 1:
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": [
                    {"type": "at", "data": {"qq": user_id}},
                    {
                        "type": "text",
                        "data": {
                            "text": ",对不起喵，你中枪了，乐可要拿走你的全部积分了喵。"
                        },
                    },
                ],
            },
        }
        bot_database.change_point(user_id,group_id, 0)
        bot_database.delete_russian_pve(user_id)
        return payload
    now_shots=now_shots-1
    now_choice = random.randint(1, now_shots)
     # 乐可开枪中枪了
    if now_choice == 1:
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": [
                    {"type": "at", "data": {"qq": user_id}},
                    {
                        "type": "text",
                        "data": {
                            "text": ",你开了一枪未中,乐可开了一枪，中了。"
                        },
                    },
                    {
                        "type": "text",
                        "data": {
                            "text": "\n乐可:怎么可能，你一定是作弊了喵！(恭喜{}赢了，积分翻倍)".format(nick_name)
                        },
                    },
                ],
            },
        }
        bot_database.change_point(user_id, group_id,bot_database.find_point(user_id)*10)
        bot_database.delete_russian_pve(user_id)
        return payload
    now_shots=now_shots-1
    bot_database.changed_russian_pve(user_id, now_shots)
    payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": [
                    {"type": "at", "data": {"qq": user_id}},
                    {
                        "type": "text",
                        "data": {
                            "text": "你开了一枪，未中；乐可开了一枪，未中。剩余子弹:{}".format(now_shots)
                        },
                    },
                ],
            },
        }
    return payload
    


def russian_pve(user_id: int, group_id: int,nick_name:str):
    if bot_database.find_point(user_id) > 0:
        now_shots = bot_database.check_russian_pve(user_id)
        if now_shots == -1:
            payload = {
                "action": "send_msg",
                "params": {
                    "group_id": group_id,
                    "message": [
                        {"type": "at", "data": {"qq": user_id}},
                        {
                            "type": "text",
                            "data": {
                                "text": "\n{},拔枪吧！午时已到！乐可可是第一神枪手喵！".format(nick_name)
                            },
                        },
                    ],
                },
            }
        else:
            payload = {
                "action": "send_msg",
                "params": {
                    "group_id": group_id,
                    "message": [
                        {
                            "type": "text",
                            "data": {"text": "{},你已经在乐可在决斗了喵，快开抢吧！".format(nick_name)},
                        },
                    ],
                },
            }
    else:
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {"text": "{},没积分？没积分不要来挑战乐可喵。".format(nick_name)},
                    },
                ],
            },
        }
    return payload


#
def russian(message: str, user_id: int, group_id: int):
    (bullet, point) = pro_str(message)
    if bullet == -1 or point == -1:
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": [
                    {"type": "at", "data": {"qq": user_id}},
                    {
                        "type": "text",
                        "data": {"text": "子弹数目必须在1~5，积分不能为负数。"},
                    },
                ],
            },
        }
    elif bullet != -1 and point == -2:
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": [
                    {"type": "at", "data": {"qq": user_id}},
                    {
                        "type": "text",
                        "data": {
                            "text": "装入{}颗子弹;未输入积分，默认全部积分：{}。".format(
                                bullet, bot_database.find_point(user_id)
                            )
                        },
                    },
                ],
            },
        }
    elif point == -2 and bullet == -2:
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": [
                    {"type": "at", "data": {"qq": user_id}},
                    {
                        "type": "text",
                        "data": {
                            "text": "经典模式，1颗子弹和全部积分:{}。".format(
                                bot_database.find_point(user_id)
                            )
                        },
                    },
                ],
            },
        }
    else:
        user_point = bot_database.find_point(user_id)
        if int(user_point) > int(point):
            payload = {
                "action": "send_msg",
                "params": {
                    "group_id": group_id,
                    "message": [
                        {"type": "at", "data": {"qq": user_id}},
                        {
                            "type": "text",
                            "data": {
                                "text": "子弹上膛，{}颗子弹，{}积分。".format(
                                    bullet, point
                                )
                            },
                        },
                    ],
                },
            }
        else:
            payload = {
                "action": "send_msg",
                "params": {
                    "group_id": group_id,
                    "message": [
                        {"type": "at", "data": {"qq": user_id}},
                        {"type": "text", "data": "积分不足，无法上膛。"},
                    ],
                },
            }
    return payload

