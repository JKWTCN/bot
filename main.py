import traceback
import json
import asyncio
from websockets.asyncio.server import serve
from schedule.schedule import Schedule
from data.message.group_message_info import GroupMesssageInfo
from data.message.private_message_info import PrivateMesssageInfo
from data.message.meta_message_info import MetaMessageInfo
from data.message.notice_message_info import NoticeMessageInfo
from data.message.request_message_info import RequestMessageInfo


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
                            privateMessageInfo = PrivateMesssageInfo(websocket, message)
                            schedule.processMessage(privateMessageInfo)
                case "notice":
                    noticeMessageInfo = NoticeMessageInfo(websocket, message)
                    schedule.processMessage(noticeMessageInfo)
                case "meta_event":
                    metaMessageInfo = MetaMessageInfo(websocket, message)
                    schedule.processMessage(metaMessageInfo)
                case "request":
                    requestMessageInfo = RequestMessageInfo(websocket, message)
                    schedule.processMessage(requestMessageInfo)
    except Exception as e:
        print(f"处理消息时出错: {e},line:{traceback.extract_tb(e.__traceback__)[0][1]}")


async def pro(websocket):
    async for message in websocket:
        print(message)
        await echo(websocket, message)


schedule = Schedule()


async def main():
    async with serve(pro, "localhost", 27434) as server:
        await server.serve_forever()


asyncio.run(main())
