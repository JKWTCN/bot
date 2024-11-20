import json
from venv import logger
import requests
from tools import HasKeyWords, dump_setting, load_setting, say, ReplySay
from Class.Group_member import get_user_name
import time


# 讲笑话
async def Joke(websocket, group_id):
    r = requests.get("https://api.vvhan.com/api/text/joke")
    print(r.text)
    await say(websocket, group_id, r.text)


# 更新冷群状态
def UpdateColdGroup(user_id: int, group_id: int, message_id: int, raw_message: str):
    setting = load_setting()
    for group in setting["cold_group_king"]:
        if group["group_id"] == group_id:
            group["user_id"] = user_id
            group["message_id"] = message_id
            group["time"] = time.time()
            group["is_replay"] = False
            group["num"] += 1
            group["raw_message"] = raw_message
            dump_setting(setting)
            return
    setting["cold_group_king"].append(
        {
            "group_id": group_id,
            "user_id": user_id,
            "message_id": message_id,
            "time": time.time(),
            "is_replay": False,
            "num": 0,
            "raw_message": raw_message,
        }
    )
    dump_setting(setting)


# 检测是否冷群
async def ColdReplay(websocket):
    setting = load_setting()
    for group in setting["cold_group_king"]:
        if (
            group["is_replay"] == False
            and time.time() - group["time"]
            >= setting["cold_group_king_setting"]["time_out"]
            and group["num"] > setting["cold_group_king_setting"]["num_out"]
            and group["group_id"] not in setting["developers_list"]
        ):
            group["is_replay"] = True
            group["num"] = 0
            dump_setting(setting)
            name = get_user_name(group["user_id"], group["group_id"])
            await ReplySay(
                websocket,
                group["group_id"],
                group["message_id"],
                ColdChat(group),
            )


# chat内容转发给大模型
def ColdChat(group: dict) -> str:
    user_id = group["user_id"]
    group_id = group["group_id"]
    num = group["num"]
    raw_message = group["raw_message"]
    if HasKeyWords(
        raw_message,
        [
            "[CQ:image",
        ],
    ):
        raw_message = ""
    nick_name = get_user_name(user_id, group_id)
    port = "11434"
    url = f"http://localhost:{port}/api/chat"
    model = "qwen2.5:0.5b"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": model,  # 模型选择
        "options": {
            "temperature": 1.0  # 为0表示不让模型自由发挥，输出结果相对较固定，>0的话，输出的结果会比较放飞自我
        },
        "stream": False,  # 流式输出
        "messages": [
            {
                "role": "system",
                "content": "你叫乐可，现在你将模仿一只傲娇的猫娘(猫娘是一种拟人化的生物，其行为似猫但类人。)，与我对话每一句话后面都要加上“喵”",
            },
            {
                "role": "User",
                "content": f"在{nick_name}说话前,群友们聊了{num}句,他说的上一句话是:{raw_message},大家前面都聊的好火热,他一说话后大家就都不说话了,快狠狠地嘲笑嘲笑他。",
            },
        ],
    }
    try:
        response = requests.post(url, json=data, headers=headers, timeout=30)
        res = response.json()
        logger.info("(AI)乐可说:{}".format(res["message"]["content"]))
        return res["message"]["content"]
    except:
        logger.info("连接超时")
        return f"{nick_name},大家前面都聊的好好的,你一说话就冷群了喵。"


# chat内容转发给大模型
async def chat(websocket, group_id: int, nick_name: str, text: str):
    port = "11434"
    url = f"http://localhost:{port}/api/chat"
    model = "qwen2.5:0.5b"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": model,  # 模型选择
        "options": {
            "temperature": 1.0  # 为0表示不让模型自由发挥，输出结果相对较固定，>0的话，输出的结果会比较放飞自我
        },
        "stream": False,  # 流式输出
        "messages": [
            {
                "role": "system",
                "content": "你叫乐可，现在你将模仿一只傲娇的猫娘(猫娘是一种拟人化的生物，其行为似猫但类人。)，与我对话每一句话后面都要加上“喵”",
            },
            {
                "role": "User",
                "content": text,
            },
        ],
    }
    try:
        response = requests.post(url, json=data, headers=headers, timeout=30)
        res = response.json()
        # print(len(response.text))
        # print(res["message"])
        logger.info("(AI)乐可说:{}".format(res["message"]["content"]))
        re_text = res["message"]["content"]

    except:
        logger.info("连接超时")
        re_text = "呜呜不太理解呢喵。"
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": "{},{}".format(nick_name, re_text),
        },
    }
    await websocket.send(json.dumps(payload))


# ollama run qwen2.5:0.5b
