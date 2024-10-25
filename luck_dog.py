from datetime import date
import random
import bot_database

choice_list = [200, 100, 50, 10, -10, -20, 444, 555, 666, 777]
choice_probability = [
    0.025,#200
    0.05,#100
    0.1,#50
    0.2,#10
    0.25,#-10
    0.25,#-20
    0.01,#*2
    0.01,#/2
    0.001,#*10
    0.001,#0
]


def ys_simple(ys):
    if ys == 0:
        return "大吉喵，快买彩票喵。"
    elif ys < 20:
        return "吉"
    elif ys < 40:
        return "小吉"
    elif ys < 70:
        return "普通"
    elif ys < 99:
        return "凶"
    elif ys == 99:
        return "大凶，快去洗澡喵"


def luck_dog(use_id: int, sender_name: str, group_id: int):
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": "{},{}。".format(
                sender_name,
                ys_simple((date.today().day * use_id) % 100),
            ),
        },
    }
    return payload


def luck_choice_mut(user_id: int, sender_name: str, group_id: int, nums: int):
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [],
        },
    }
    for i in range(nums):
        now_point = bot_database.find_point(user_id)
        if now_point >= 5:
            bot_database.add_gambling_times(user_id, 1)
            now_point = now_point - 5
            choice = random.choices(choice_list, choice_probability)
            if choice[0] == 666:
                changed_point = now_point * 10
                payload["params"]["message"].append(
                    {
                        "type": "text",
                        "data": {
                            "text": "{},积分{}->{},10倍大奖喵。\n".format(
                                sender_name, now_point, changed_point
                            )
                        },
                    }
                )
            elif choice[0] == 777:
                changed_point = 0
                payload["params"]["message"].append(
                    {
                        "type": "text",
                        "data": {
                            "text": "{},赌狗好似喵,积分清零喵。\n".format(sender_name)
                        },
                    }
                )
            elif choice[0] == 444:
                changed_point = now_point * 2
                payload["params"]["message"].append(
                    {
                        "type": "text",
                        "data": {
                            "text": "{},积分{}->{},二倍奖喵。\n".format(
                                sender_name, now_point, changed_point
                            )
                        },
                    }
                )
            elif choice[0] == 555:
                changed_point = now_point / 2
                payload["params"]["message"].append(
                    {
                        "type": "text",
                        "data": {
                            "text": "{},积分{}->{},折半奖喵。\n".format(
                                sender_name, now_point, changed_point
                            )
                        },
                    }
                )
            else:
                changed_point = now_point + choice[0]
                if changed_point >= 0:
                    payload["params"]["message"].append(
                        {
                            "type": "text",
                            "data": {
                                "text": "{},抽奖成功喵,积分{}->{}。\n".format(
                                    sender_name, now_point, changed_point
                                )
                            },
                        }
                    )
                else:
                    payload["params"]["message"].append(
                        {
                            "type": "text",
                            "data": {
                                "text": "{},积分{}->{},十赌九输喵,负债累累喵。\n".format(
                                    sender_name, now_point, changed_point
                                )
                            },
                        }
                    )
            bot_database.change_point(user_id, changed_point)
            if changed_point <= 0:
                return payload
        else:
            payload["params"]["message"].append(
                {
                    "type": "text",
                    "data": {
                        "text": "{},抽奖失败喵，至少要5积分喵。您当前积分为：{}。\n".format(
                            sender_name, now_point
                        )
                    },
                }
            )
            return payload
    # print(payload)
    return payload


# 5积分抽一次
# 200(0.025) 100(0.05) 50(0.10) 10(0.20) -10(0.5) 10*(0.001) 0*(0.001)
def luck_choice(user_id: int, sender_name: str, group_id: int):
    now_point = bot_database.find_point(user_id)
    if now_point >= 5:
        bot_database.add_gambling_times(user_id, 1)
        now_point = now_point - 5
        choice = random.choices(choice_list, choice_probability)
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": "",
            },
        }
        if choice[0] == 666:
            changed_point = now_point * 10
            payload["params"]["message"] = "{},积分{}->{},10倍大奖喵。".format(
                sender_name, now_point, changed_point
            )
        elif choice[0] == 777:
            changed_point = 0
            payload["params"]["message"] = "{},赌狗好似喵,积分清零喵。".format(
                sender_name
            )
        elif choice[0] == 444:
            changed_point = now_point * 2
            payload["params"]["message"] = "{},积分{}->{},二倍奖喵。".format(
                sender_name, now_point, changed_point
            )
        elif choice[0] == 555:
            changed_point = now_point / 2
            payload["params"]["message"] = "{},积分{}->{},折半奖喵。".format(
                sender_name, now_point, changed_point
            )
        else:
            changed_point = now_point + choice[0]
            if changed_point >= 0:
                payload["params"]["message"] = "{},抽奖成功喵,积分{}->{}。".format(
                    sender_name, now_point, changed_point
                )
            else:
                payload["params"]["message"] = (
                    "{},积分{}->{},十赌九输喵,负债累累喵。".format(
                        sender_name, now_point, changed_point
                    )
                )
        bot_database.change_point(user_id, changed_point)
    else:
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": "{},抽奖失败喵，至少要5积分喵。您当前积分为：{}。".format(
                    sender_name, now_point
                ),
            },
        }
    # print(payload)
    return payload

