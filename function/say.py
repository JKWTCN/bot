import base64
import json
import logging
import re

import requests


# 图片回复
async def SayImgReply(
    websocket, user_id: int, group_id: int, message_id: int, text: str, img_path: str
):
    with open(img_path, "rb") as image_file:
        image_data = image_file.read()
    image_base64 = base64.b64encode(image_data)
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": message_id}},
                {
                    "type": "text",
                    "data": {"text": text},
                },
                {
                    "type": "image",
                    "data": {"file": "base64://" + image_base64.decode("utf-8")},
                },
            ],
        },
    }
    await websocket.send(json.dumps(payload))


def SayGroupReturnMessageId(groupId: int, text: str):
    """发送群消息并返回消息ID

    Args:
        groupId (int): 群组ID
        text (str): 消息内容

    Returns:
        int: 消息ID
    """
    payload = {
        "group_id": groupId,
        "message": [{"type": "text", "data": {"text": text}}],
    }
    response = requests.post("http://localhost:27433/send_group_msg", json=payload)
    data = response.json()
    return data["data"]["message_id"]


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


async def SayRaw(websocket, group_id: int, payload: dict):
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


async def SayGroup(websocket, group_id: int, text: str):
    """发送纯文本的群聊消息

    Args:
        websocket (_type_): 要回复的websocket
        group_id (int): 群聊id
        text (str): 回复的纯文本内容
    """
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


def chatNoContext(texts):
    """只处理单句"""
    port = "11434"
    url = f"http://localhost:{port}/api/chat"
    model = "qwen3:8b"
    headers = {"Content-Type": "application/json"}

    # 构建基础消息结构
    base_messages = [
        {
            "role": "system",
            "content": "你叫乐可,现在你将模仿一只傲娇并且温柔的猫娘(猫娘是一种拟人化的生物,其行为似猫但类人.),与我对话每一句话后面都要加上'喵'",
        }
    ]
    for text in texts:
        base_messages.append(
            {
                "role": "user",
                "content": text,
            }
        )

    data = {
        "model": model,
        "options": {"temperature": 1.0},
        "stream": False,
        "messages": base_messages,
    }

    # 特殊模型处理
    if model == "qwen3:8b":
        for msg in data["messages"]:
            if msg["role"] == "system":
                msg["content"] = "/nothink " + msg["content"]
            elif msg["role"] == "user":
                msg["content"] = "/nothink " + msg["content"]

    try:
        print(data)
        response = requests.post(url, json=data, headers=headers, timeout=300)
        res = response.json()

        if model != "deepseek-r1:1.5b" and model != "qwen3:8b":
            re_text = res["message"]["content"]
        else:
            match = re.findall(
                r"<think>([\s\S]*)</think>([\s\S]*)",
                res["message"]["content"],
            )
            re_text = match[0][1]
    except:
        logging.info("连接超时")
        re_text = "呜呜不太理解呢喵."

    # 清理回复中的换行符
    while "\n" in re_text:
        re_text = re_text.replace("\n", "")

    logging.info("(AI)乐可思考图片结果:{}".format(re_text))
    return re_text
