import bot_database


def poor_point(user_id: int, group_id: int, sender_name: str):
    now_point = bot_database.find_point(user_id)
    if now_point <= 0:
        bot_database.change_point(user_id,group_id, 5)
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": "{},领取群低保成功喵，目前你的积分为:5。".format(
                    sender_name
                ),
            },
        }
    else:
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": "{},你不符合群低保领取条件。".format(sender_name),
            },
        }
    return payload
