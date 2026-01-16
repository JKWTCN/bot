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
from tools.tools import load_setting


async def echo(websocket, message):
    try:
        message = json.loads(message)
        if not load_setting("debug_mode", False):
            print(f"收到消息: {message}")  # 打印接收到的消息内容
        else:
            logging.info(f"收到消息: {message}")
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
                            if len(groupMessageInfo.imageFileList) != 0 and get_config(
                                "image_parsing", groupMessageInfo.groupId
                            ):
                                # 处理图片消息
                                from function.image_processor import process_image_message
                                text_message = process_image_message(message, websocket)
                                if text_message is not None:
                                    # 立即处理的情况（已缓存或未开启解析）
                                    write_message(message, text_message)

                            else:
                                write_message(message, groupMessageInfo.readMessage)
                            if groupMessageInfo.senderId in get_config(
                                "no_reply_list", groupMessageInfo.groupId
                            ):  # type: ignore
                                if not load_setting("debug_mode", False):
                                    print(
                                        f"机器人ID:{groupMessageInfo.senderId},其他机器人不理睬。"
                                    )
                                else:
                                    logging.info(
                                        f"机器人ID:{groupMessageInfo.senderId},其他机器人不理睬。"
                                    )
                                return
                            # if groupMessageInfo.groupId == 755652553:
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
        logging.error("发生错误: %s", e, exc_info=True)


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
    # 删除临时文件夹 images 内的所有文件
    import shutil
    if os.path.exists("images"):
        shutil.rmtree("images")
    os.makedirs("images", exist_ok=True)
    setup_logging()
    initApplications()
    # 初始化图片处理数据库
    from function.image_processor import init_database
    init_database()


    async with serve(pro, "0.0.0.0", GetNCWCPort()) as server:
        await server.serve_forever()


asyncio.run(main())
