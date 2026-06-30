from datetime import datetime
import contextlib
import logging
import os
import signal
import traceback
import json
import asyncio
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed
from schedule.schedule import Schedule
from data.message.group_message_info import GroupMessageInfo
from data.message.private_message_info import PrivateMesssageInfo
from data.message.meta_message_info import MetaMessageInfo
from data.message.notice_message_info import NoticeMessageInfo
from data.message.request_message_info import RequestMessageInfo

from registered_application_list import initApplications
from function.GroupConfig import get_config
from function.database_message_async import write_message
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
                            await AddChatRecord(
                                groupMessageInfo.senderId, groupMessageInfo.groupId
                            )
                            if len(groupMessageInfo.imageFileList) != 0 and get_config(
                                "image_parsing", groupMessageInfo.groupId
                            ):
                                # 处理图片消息 - 使用异步版本避免阻塞主线程
                                from function.image_processor import (
                                    process_image_message_async,
                                )

                                text_message = await process_image_message_async(
                                    message, websocket
                                )
                                if text_message is not None:
                                    # 立即处理的情况（已缓存或未开启解析）
                                    await write_message(message, text_message)

                            else:
                                await write_message(message, groupMessageInfo.readMessage)
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
                            elif get_config("silent_mode", groupMessageInfo.groupId):
                                return
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
    """WebSocket连接处理函数（带异常处理）"""
    try:
        async for message in websocket:
            await echo(websocket, message)
    except ConnectionClosed as e:
        logging.warning(f"WebSocket连接关闭: {e}")
    except Exception as e:
        logging.error(f"WebSocket处理错误: {e}", exc_info=True)


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


def install_stop_signal_handlers(stop_event: asyncio.Event):
    """注册 SIGINT/SIGTERM 停止信号。"""
    loop = asyncio.get_running_loop()
    for stop_signal in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(stop_signal, stop_event.set)


async def cancel_pending_tasks():
    """取消当前任务之外的后台任务,避免事件循环关闭时仍有 pending task。"""
    current_task = asyncio.current_task()
    pending_tasks = [
        task
        for task in asyncio.all_tasks()
        if task is not current_task and not task.done()
    ]
    if not pending_tasks:
        return

    for task in pending_tasks:
        task.cancel()

    await asyncio.gather(*pending_tasks, return_exceptions=True)


async def close_server_gracefully(server):
    """显式关闭 websocket server 并等待底层 close task 完成。"""
    if server is None:
        return
    server.close()
    try:
        await asyncio.wait_for(server.wait_closed(), timeout=15.0)
    except asyncio.TimeoutError:
        logging.warning("WebSocket server 关闭超时,继续退出")


async def main():

    # 删除临时文件夹
    import shutil

    if os.path.exists("images"):
        shutil.rmtree("images")
    os.makedirs("images", exist_ok=True)
    if os.path.exists("downloads"):
        shutil.rmtree("downloads")
    os.makedirs("downloads", exist_ok=True)
    setup_logging()

    # 初始化数据库 WAL 模式和优化配置
    from database.db_init import init_all_databases

    init_all_databases()

    from database.db_pool import init_pools, close_pools

    await init_pools()

    from config.config_cache import config_cache

    # 预加载配置
    _ = await config_cache.get(
        "bot_config",
        lambda: json.load(open("static_setting.json", "r", encoding="utf-8")),
    )
    _ = await config_cache.get(
        "intelligence_config",
        lambda: json.load(open("intelligence_config.json", "r", encoding="utf-8")),
    )

    from intelligence.memory.batch_processor import init_memory_batch_processor

    await init_memory_batch_processor()

    initApplications()
    # 初始化图片处理数据库
    from function.image_processor import init_database

    init_database()
    from function.emoji_store import init_emoji_database

    init_emoji_database()

    stop_event = asyncio.Event()
    install_stop_signal_handlers(stop_event)
    server = None

    try:
        server = await serve(
            pro,
            "0.0.0.0",
            GetNCWCPort(),
            ping_timeout=30,  # 30秒ping超时
            close_timeout=10,
        )
        logging.info("WebSocket server 已启动,监听端口:%s", GetNCWCPort())
        await stop_event.wait()
    except asyncio.CancelledError:
        logging.info("主任务收到取消信号,开始关闭")
    finally:
        await close_server_gracefully(server)
        await cancel_pending_tasks()
        await close_pools()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
