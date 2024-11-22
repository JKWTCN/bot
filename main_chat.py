import asyncio
import json
import logging
import requests
import websockets

from websocket import create_connection


from tools import GetLogTime


async def main_chat():
    async with websockets.serve(chat_echo, "0.0.0.0", 27432):
        await asyncio.get_running_loop().create_future()  # run forever


async def chat_echo(websocket):
    async for message in websocket:
        await websocket.send(json.dumps({"status": "ok"}))
        logging.info(message)
        message = json.loads(message)
        if "message_id" in message:
            group_id = message["group_id"]
            message_id = message["message_id"]
            data = message["data"]
            port = "11434"
            url = f"http://localhost:{port}/api/chat"
            headers = {"Content-Type": "application/json"}
            try:
                response = requests.post(url, json=data, headers=headers, timeout=30000)
                res = response.json()
                logging.info("(AI)乐可说:{}".format(res["message"]["content"]))
                re_text = res["message"]["content"]
            except:
                logging.info("连接超时")
                re_text = "呜呜不太理解呢喵。"
            ws = create_connection("ws://127.0.0.1:27431")
            re_message = {
                "action": "reply_chat",
                "group_id": group_id,
                "message_id": message_id,
                "message": re_text,
            }
            ws.send(json.dumps(re_message))


LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%m/%d/%Y %H:%M:%S %p"
now = GetLogTime()
logging.basicConfig(
    filename=f"log/{now}_chat.log",
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    encoding="utf-8",
)
asyncio.run(main_chat())
