def get_group_member_info(group_id: int):
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [],
        },
    }
    return payload


def get_group_member_list(group_id: int):
    payload = {
        "action": "get_group_member_list",
        "params": {
            "group_id": group_id,
        },
    }
    return payload


def kick_member(user_id: int, group_id: int):
    payload = {
        "action": "set_group_kick",
        "params": {
            "user_id": user_id,
            "group_id": group_id,
        },
    }
    # print(payload)
    return payload
