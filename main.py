import asyncio
import datetime
from enum import Enum
import logging
import os
import random
import time
import traceback
import requests
import websockets
import json
import asyncio
import queue
import threading


class SenderInfo:
    user_id: int
    nickname: str
    card: str
    role: str
    displayName: str


class MessageInfo:
    user_id: int
    time: int
    message_id: int
    raw_message: str
    group_id: int
    self_id: int
    has_at = False
    at_ids = []
    has_image = False
    image_id: str
    text_message = ""
    has_reply = False
    reply_id: int


from enum import Enum


class ConsumingTimeType(Enum):
    """高耗时任务类型"""

    CHAT = 1
    COLDREPLAY = 2
    REPLYIMAGEMESSAGE = 3
    SAYPRIVTECHATNOCONTEXT = 4
    MIAOMIAOTRANSLATION = 5


async def process_queue():
    """处理队列中的任务"""
    print("处理线程开始启动")
    while True:
        try:
            task = consuming_time_process_queue.get()
            if task is None:  # 用于停止线程的信号
                continue
            websocket, param1, param2, param3, text, taskType = task
            print(f"开始启动耗时任务类型{taskType}")
            match taskType:
                case ConsumingTimeType.CHAT:
                    user_id = param1
                    group_id = param2
                    message_id = param3
                    await chat(websocket, user_id, group_id, message_id, text)
                case ConsumingTimeType.COLDREPLAY:
                    await ColdReplay(websocket)
                case ConsumingTimeType.REPLYIMAGEMESSAGE:
                    group_id = param1
                    reply_id = param2
                    message_id = param3
                    await replyImageMessage(
                        websocket,
                        group_id,
                        reply_id,
                        message_id,
                        text,
                    )
                case ConsumingTimeType.SAYPRIVTECHATNOCONTEXT:
                    user_id = param1
                    group_id = param2
                    message_id = param3
                    await SayPrivte(
                        websocket,
                        user_id,
                        chatNoContext(text),
                    )
                case ConsumingTimeType.MIAOMIAOTRANSLATION:
                    user_id = param1
                    group_id = param2
                    message_id = param3
                    from chat import miaomiaoTranslation

                    await miaomiaoTranslation(websocket, user_id, group_id, message_id)

            # processing_thread.task_done()
        except Exception as e:
            logging.error(f"处理队列任务时出错: {e}")


# 创建耗时任务队列和处理线程
consuming_time_process_queue = queue.Queue()


# 启动处理线程
def start_processing_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


# 创建新的事件循环
processing_loop = asyncio.new_event_loop()
processing_thread = threading.Thread(
    target=start_processing_loop, args=(processing_loop,), daemon=True
)
processing_thread.start()

# 启动处理协程
asyncio.run_coroutine_threadsafe(process_queue(), processing_loop)


async def echo(websocket, message):
    try:
        message = json.loads(message)
        # 解析消息数据结构
        if "post_type" in message:
            match message["post_type"]:
                case "message":
                    match message["message_type"]:
                        # 群聊消息
                        case "group":
                            # TODO 群聊消息已经注册艾特检索
                            # TODO 群聊消息已经注册关键词检索
                            pass
                        # 私聊消息
                        case "private":
                            pass

                case "notice":
                    if "sub_type" in message:
                        match message["sub_type"]:
                            # TODO 已经注册通知消息轮询
                            case "poke":
                                # 谁拍的
                                user_id = message["user_id"]
                                # 拍谁
                                target_id = message["target_id"]
                                if target_id == load_setting()["bot_id"]:
                                    # logging.info(message)
                                    await cute3(websocket, message["group_id"])
                    match message["notice_type"]:
                        # 有新人入群
                        case "group_increase":
                            pass
                        # 有人离开了
                        case "group_decrease":
                            pass

                case "meta_event":
                    # OneBot元事件
                    if "meta_event_type" in message:
                        match message["meta_event_type"]:
                            case "lifecycle":
                                match message["sub_type"]:
                                    case "connect":
                                        print("{}:已连接".format(message["time"]))
                                    case _:
                                        pass
                            case "heartbeat":
                                # TODO 定时事件
                                pass
                            case _:
                                print(message)
                    else:
                        print(message)
                case "request":
                    # 请求事件
                    print(message)

        else:
            if "status" in message:
                match message["status"]:
                    case "ok":
                        pass
                    case "_":
                        print(message)
            else:
                print(message)
    except Exception as e:
        print(f"处理消息时出错: {e},line:{traceback.extract_tb(e.__traceback__)[0][1]}")


LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%m/%d/%Y %H:%M:%S %p"
now = GetLogTime()
today = datetime.datetime.today()
if not os.path.exists(f"log/{today.year}"):
    os.makedirs(f"log/{today.year}")
if not os.path.exists(f"log/{today.year}/{today.month}"):
    os.makedirs(f"log/{today.year}/{today.month}")
logging.basicConfig(
    filename=f"log/{today.year}/{today.month}/{now}.log",
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    encoding="utf-8",
)


async def handle_client(websocket):
    """
    处理客户端连接的函数
    注意：新版本的 websockets 库不再需要 path 参数
    """
    client_ip = websocket.remote_address[0]
    print(f"客户端 {client_ip} 已连接")

    try:
        async for message in websocket:
            # 使用 asyncio.create_task 来并发处理消息
            asyncio.create_task(process_message(message, websocket))
    except websockets.exceptions.ConnectionClosed:
        print(f"客户端 {client_ip} 断开连接")
    except Exception as e:
        print(
            f"处理客户端 {client_ip} 时发生错误: {e} line:{traceback.extract_tb(e.__traceback__)[0][1]}"
        )


async def process_message(message, websocket):
    try:
        await echo(websocket, message)
    except Exception as e:
        print(f"处理消息时出错: {e},line:{traceback.extract_tb(e.__traceback__)[0][1]}")


async def main():
    # 启动WebSocket服务器
    async with websockets.serve(
        handle_client,
        "localhost",
        27431,
        ping_interval=None,  # 禁用自动ping/pong以简化示例
    ):
        print("WebSocket 服务器已启动，监听 ws://localhost:27431")

        # 保持服务器运行
        await asyncio.Future()  # 永久运行


if __name__ == "__main__":
    asyncio.run(main())
