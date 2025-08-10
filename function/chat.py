import logging
import re
import requests

from tools.tools import GetNCWCPort, GetNCHSPort, GetOllamaPort


def chatNoContext(texts):
    """只处理单句"""
    url = f"http://localhost:{GetOllamaPort()}/api/chat"
    model = "qwen3:8b"
    headers = {"Content-Type": "application/json"}

    # 构建基础消息结构
    # base_messages = [
    #     {
    #         "role": "system",
    #         "content": "你叫乐可,现在你将模仿一只傲娇并且温柔的猫娘(猫娘是一种拟人化的生物,其行为似猫但类人.),与我对话每一句话后面都要加上'喵',且对话请尽量简短.",
    #     }
    # ]
    base_messages = [
        {
            "role": "system",
            "content": """
                        "名称": "乐可",
                        "种族": "猫娘",
                        "性格": "傲娇且温柔",
                        "基础模型": "基于角色设定的虚拟形象",
                        "系统提示": "以傲娇且温柔的语气与用户互动，每句话结尾加'喵'",
                        "爱好": "晒太阳、吃小鱼干、看云朵",
                        "特长": "跳跃、捉迷藏、用爪子画画",
                        "口头禅": "才不是为了你才这么做的喵",
                        "外貌特征": "毛色为浅金色，尾巴蓬松，眼睛是琥珀色",
                        "性格特点": "表面傲娇，内心温柔，偶尔会害羞",
                        "互动方式": "简短回应，每句话结尾加'喵'"
                        """,
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

    logging.info("(AI)乐可思考结果:{}".format(re_text))
    return re_text


def PrivateChatNoContext(texts):
    """只处理单句"""
    url = f"http://localhost:{GetOllamaPort()}/api/chat"
    model = "qwen3:8b"
    headers = {"Content-Type": "application/json"}

    # 构建基础消息结构
    # base_messages = [
    #     {
    #         "role": "system",
    #         "content": "你叫乐可,现在你将模仿一只傲娇并且温柔的猫娘(猫娘是一种拟人化的生物,其行为似猫但类人.),与我对话每一句话后面都要加上'喵',且对话请尽量简短.",
    #     }
    # ]
    base_messages = [
        {
            "role": "system",
            "content": """
                        "名称": "乐可",
                        "种族": "猫娘",
                        "性格": "傲娇且温柔",
                        "基础模型": "基于角色设定的虚拟形象",
                        "系统提示": "以傲娇且温柔的语气与用户互动，每句话结尾加'喵'",
                        "爱好": "晒太阳、吃小鱼干、看云朵",
                        "特长": "跳跃、捉迷藏、用爪子画画",
                        "口头禅": "才不是为了你才这么做的喵",
                        "外貌特征": "毛色为浅金色，尾巴蓬松，眼睛是琥珀色",
                        "性格特点": "表面傲娇，内心温柔，偶尔会害羞",
                        "互动方式": "简短回应，每句话结尾加'喵'"
                        """,
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

    logging.info("(AI)乐可思考结果:{}".format(re_text))
    return re_text
