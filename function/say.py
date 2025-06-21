import base64
import json


async def ReplySay(websocket, group_id: int, message_id: int, text: str):
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


async def SayPrivte(websocket, user_id: int, text: str):
    """私聊发言

    Args:
        websocket (websocket): 回复的websocket
        user_id (int): 回复的user_id
        text (str): 回复的纯文字内容
    """
    payload = {
        "action": "send_msg_async",
        "params": {
            "user_id": user_id,
            "message": text,
        },
    }
    await websocket.send(json.dumps(payload))


async def sayRaw(websocket, group_id: int, payload: dict):
    """发送数组类型的群消息

    Args:
        websocket (_type_): 发送的webstocket
        group_id (int): 发送的群组id
        payload (dict): 发送的数组内容
    """
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": payload,
        },
    }
    await websocket.send(json.dumps(payload))


async def say(websocket, group_id: int, text: str):
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": text,
        },
    }
    await websocket.send(json.dumps(payload))


async def SayAndAt(websocket, user_id: int, group_id: int, text: str):
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {"type": "text", "data": {"text": " " + text}},
            ],
        },
    }
    await websocket.send(json.dumps(payload))


async def SayAndAtImage(
    websocket, user_id: int, group_id: int, text: str, file_dir: str
):
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {"type": "text", "data": {"text": " " + text}},
            ],
        },
    }
    with open(file_dir, "rb") as image_file:
        image_data = image_file.read()
    image_base64 = base64.b64encode(image_data)
    payload["params"]["message"].append(
        {
            "type": "image",
            "data": {"file": "base64://" + image_base64.decode("utf-8")},
        }
    )
    await websocket.send(json.dumps(payload))


async def SayAndAtDefense(websocket, user_id: int, group_id: int, text: str):
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {"type": "text", "data": {"text": " " + text}},
            ],
        },
        "echo": "defense",
    }
    await websocket.send(json.dumps(payload))


async def delete_msg(websocket, message_id: int):
    print(f"正在撤回消息:message_id{message_id}")
    payload = {
        "action": "delete_msg",
        "params": {
            "message_id": message_id,
        },
    }
    await websocket.send(json.dumps(payload))
