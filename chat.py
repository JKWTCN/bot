from venv import logger
import requests

# chat内容转发给大模型
def chat(group_id: int, nick_name: str, text: str):
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
    except requests.exceptions.RequestException as e:
        logger.info("连接超时")
        re_text = "呜呜不太理解呢喵。"
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": "{},{}".format(nick_name, re_text),
        },
    }
    return payload


# ollama run qwen2.5:0.5b
