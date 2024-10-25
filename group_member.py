
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
