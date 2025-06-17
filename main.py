import asyncio
from enum import Enum
import logging
import traceback
import json
import asyncio
import queue
import threading
from data.message.group_message_info import GroupMesssageInfo


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


from schedule.schedule import Schedule
from data.message.private_message import PrivateMesssageInfo


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
                            groupMessageInfo = GroupMesssageInfo(websocket, message)
                            schedule.processMessage(groupMessageInfo)
                        # 私聊消息
                        case "private":
                            privateMessageInfo = PrivateMesssageInfo(message)
                            schedule.processMessage(privateMessageInfo)

                case "notice":
                    if "sub_type" in message:
                        match message["sub_type"]:
                            # TODO 已经注册通知消息轮询
                            case "poke":
                                pass
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


import asyncio
from websockets.asyncio.server import serve


async def pro(websocket):
    async for message in websocket:
        print(message)
        await echo(websocket, message)


schedule = Schedule()


def schedule_init():

    pass


async def main():
    schedule_init()
    async with serve(pro, "localhost", 27434) as server:
        await server.serve_forever()


asyncio.run(main())
