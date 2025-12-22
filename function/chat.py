import logging
import re
import requests

from tools.tools import GetNCWCPort, GetNCHSPort, GetOllamaPort


def chatNoContext(texts):
    """只处理单句"""
    model = "qwen3-vl:8b"

    # 构建基础消息结构
    from application.chat_application import getPrompts

    base_messages = [
        {
            "role": "system",
            "content": getPrompts(),
        }
    ]
    for text in texts:
        base_messages.append(
            {
                "role": "user",
                "content": text,
            }
        )

    try:
        import ollama

        print(f"使用模型: {model}, 消息: {base_messages}")
        response = ollama.chat(
            model=model,
            messages=base_messages,
            options={'temperature': 1.0}
        )

        if model != "deepseek-r1:1.5b" and model != "qwen3:8b":
            re_text = response['message']['content']
        else:
            match = re.findall(
                r"<think>([\s\S]*)</think>([\s\S]*)",
                response['message']['content'],
            )
            if match:
                re_text = match[0][1]
            else:
                re_text = response['message']['content'].strip()
    except Exception as e:
        logging.error(f"调用Ollama时出错: {str(e)}")
        re_text = "呜呜不太理解呢喵."

    # 清理回复中的换行符
    while "\n" in re_text:
        re_text = re_text.replace("\n", "")

    logging.info("(AI)乐可思考结果:{}".format(re_text))
    return re_text


def PrivateChatNoContext(texts):
    """只处理单句"""
    model = "qwen3-vl:8b"

    # 构建基础消息结构
    from application.chat_application import getPrompts

    base_messages = [
        {
            "role": "system",
            "content": getPrompts(),
        }
    ]
    for text in texts:
        base_messages.append(
            {
                "role": "user",
                "content": text,
            }
        )

    try:
        import ollama

        print(f"使用模型: {model}, 消息: {base_messages}")
        response = ollama.chat(
            model=model,
            messages=base_messages,
            options={'temperature': 1.0}
        )

        if model != "deepseek-r1:1.5b" and model != "qwen3:8b":
            re_text = response['message']['content']
        else:
            match = re.findall(
                r"<think>([\s\S]*)</think>([\s\S]*)",
                response['message']['content'],
            )
            if match:
                re_text = match[0][1]
            else:
                re_text = response['message']['content'].strip()
    except Exception as e:
        logging.error(f"调用Ollama时出错: {str(e)}")
        re_text = "呜呜不太理解呢喵."

    # 清理回复中的换行符
    while "\n" in re_text:
        re_text = re_text.replace("\n", "")

    logging.info("(AI)乐可思考结果:{}".format(re_text))
    return re_text
