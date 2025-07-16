from datetime import datetime
import logging
import os
import traceback
import json
import asyncio
from websockets.asyncio.server import serve
from schedule.schedule import Schedule
from data.message.group_message_info import GroupMessageInfo
from data.message.private_message_info import PrivateMesssageInfo
from data.message.meta_message_info import MetaMessageInfo
from data.message.notice_message_info import NoticeMessageInfo
from data.message.request_message_info import RequestMessageInfo

from registered_application_list import initApplications
from function.GroupConfig import get_config
from function.database_message import write_message
from function.chat_record import AddChatRecord


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
                            groupMessageInfo = GroupMessageInfo(websocket, message)
                            # 增加水群次数
                            AddChatRecord(
                                groupMessageInfo.senderId, groupMessageInfo.groupId
                            )
                            if (
                                len(groupMessageInfo.imageFileList) != 0
                                and get_config(
                                    "image_parsing", groupMessageInfo.groupId
                                )
                                == False
                            ):
                                write_message(message, groupMessageInfo.readMessage)
                            else:
                                # TODO image-image移植
                                pass
                            if groupMessageInfo.senderId in get_config(
                                "no_reply_list", groupMessageInfo.groupId
                            ):  # type: ignore
                                print(
                                    f"机器人ID:{groupMessageInfo.senderId},其他机器人不理睬。"
                                )
                                return
                            if groupMessageInfo.groupId == 755652553:
                                print(message)
                                await schedule.processMessage(groupMessageInfo)
                        # 私聊消息
                        case "private":
                            privateMessageInfo = PrivateMesssageInfo(websocket, message)
                            await schedule.processMessage(privateMessageInfo)
                case "notice":
                    noticeMessageInfo = NoticeMessageInfo(websocket, message)
                    await schedule.processMessage(noticeMessageInfo)
                case "meta_event":
                    metaMessageInfo = MetaMessageInfo(websocket, message)
                    await schedule.processMessage(metaMessageInfo)
                case "request":
                    requestMessageInfo = RequestMessageInfo(websocket, message)
                    await schedule.processMessage(requestMessageInfo)
    except Exception as e:
        print(f"处理消息时出错: {e},line:{traceback.extract_tb(e.__traceback__)[0][1]}")


async def pro(websocket):
    async for message in websocket:
        await echo(websocket, message)


schedule = Schedule()

from tools.tools import GetNCWCPort, GetNCHSPort, GetOllamaPort


def setup_logging():
    # 获取当前日期
    now = datetime.now()

    # 构建日志路径
    log_dir = os.path.join(
        "log", now.strftime("%Y"), now.strftime("%m")  # 四位年份  # 两位月份
    )

    # 创建目录（如果不存在）
    os.makedirs(log_dir, exist_ok=True)

    # 日志文件名（日期.log）
    log_file = os.path.join(log_dir, f"{now.strftime('%d')}.log")

    # 配置logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),  # 同时输出到控制台
        ],
    )


async def main():
    setup_logging()
    initApplications()
    async with serve(pro, "localhost", GetNCWCPort()) as server:
        await server.serve_forever()


asyncio.run(main())
