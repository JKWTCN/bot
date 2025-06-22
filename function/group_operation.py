import json


async def banNormal(websocket, user_id: int, group_id: int, duration: int):
    """禁言群友(对管理无效,也不会提示)"""
    from function.datebase_user import IsAdmin

    if IsAdmin(user_id, group_id):
        pass
    else:
        payload = {
            "action": "set_group_ban",
            "params": {"group_id": group_id, "user_id": user_id, "duration": duration},
        }
        await websocket.send(json.dumps(payload))


async def ban_new(websocket, user_id: int, group_id: int, duration: int):
    from function.datebase_user import IsAdmin

    if IsAdmin(user_id, group_id):
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": "我，打管理?真的假的?",
            },
        }
        await websocket.send(json.dumps(payload))
    else:
        payload = {
            "action": "set_group_ban",
            "params": {"group_id": group_id, "user_id": user_id, "duration": duration},
        }
        await websocket.send(json.dumps(payload))


async def ReplySayGroup(websocket, group_id: int, message_id: int, text: str):
    """引用回复

    Args:
        websocket (websocket): 回复的webstocket
        group_id (int): 发言的群号
        message_id (int): 引用回复的消息ID
        text (str): 发言的纯文字内容
    """
    payload = {
        "action": "send_group_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": message_id}},
                {
                    "type": "text",
                    "data": {"text": text},
                },
            ],
        },
    }
    await websocket.send(json.dumps(payload))
