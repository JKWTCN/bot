import base64
import json
import logging
import asyncio
import random
from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.say import SayRaw, SayGroup
from tools.tools import FindNum, load_setting
from tools.file_list_cache import file_cache


async def SendSingleMeme(websocket, groupId: int):
    try:
        # 使用缓存获取文件列表（30分钟内不重复扫描）
        all_file = await file_cache.get_image_files(load_setting("meme_path", ""))
        logging.info("读取目录完毕")

        payload = {
            "action": "send_forward_msg",
            "params": {
                "message_type": "group",
                "group_id": groupId,
                "message": [],
            },
        }

        # 异步读取图片（不阻塞事件循环）
        dir = random.choice(all_file)
        loop = asyncio.get_event_loop()
        image_data = await loop.run_in_executor(None, lambda: open(dir, "rb").read())
        image_base64 = base64.b64encode(image_data)

        payload["params"]["message"].append(
            {
                "type": "image",
                "data": {"file": "base64://" + image_base64.decode("utf-8")},
            }
        )
        await websocket.send(json.dumps(payload))
    except Exception as e:
        logging.error(e)
        await SayGroup(websocket, groupId, f"图片发送失败了喵。")


async def SendMemeMergeForwarding(websocket, group_id: int, nums: int):
    """发送随机梗图合并转发消息"""
    try:
        # 使用缓存获取文件列表（已过滤扩展名，30分钟内不重复扫描）
        all_file = await file_cache.get_image_files(load_setting("meme_path", ""))
        logging.info("读取目录完毕")

        payload = {
            "action": "send_forward_msg",
            "params": {
                "message_type": "group",
                "group_id": group_id,
                "message": [],
            },
        }

        # 确保不超过可用文件数量
        actual_nums = min(nums, len(all_file))

        # 使用 random.sample() 单次多连内无重复选择
        selected_files = random.sample(all_file, actual_nums)
        loop = asyncio.get_event_loop()

        for i, dir in enumerate(selected_files):
            print(dir)
            logging.info("剩余发送{}张，发送了图片:{}".format(actual_nums - i - 1, dir))

            # 异步读取图片（不阻塞事件循环）
            image_data = await loop.run_in_executor(None, lambda: open(dir, "rb").read())
            image_base64 = base64.b64encode(image_data)

            payload["params"]["message"].append(
                {
                    "type": "node",
                    "data": {
                        "user_id": load_setting("bot_id", 0),
                        "nickname": "乐可",
                        "content": [
                            {
                                "type": "image",
                                "data": {
                                    "file": "base64://" + image_base64.decode("utf-8")
                                },
                            }
                        ],
                    },
                }
            )
        await websocket.send(json.dumps(payload))
    except Exception as e:
        logging.error(e)
        await SayGroup(websocket, group_id, f"图片发送失败了喵。")


from tools.tools import HasAllKeyWords, HasKeyWords


class RadomMemeApplication(GroupMessageApplication):
    def __init__(
        self,
    ):
        applicationInfo = ApplicationInfo("随机梗图功能", "触发:梗图X连")
        super().__init__(applicationInfo, 10, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        num = FindNum(message.plainTextMessage)
        import math

        num = math.trunc(num)
        if num > 50:
            await SayGroup(
                message.websocket,
                message.groupId,
                "最大50连喵！",
            )
        elif num == -1:
            await SendSingleMeme(message.websocket, message.groupId)
        else:
            nums = num
            await SendMemeMergeForwarding(
                message.websocket,
                message.groupId,
                nums,
            )
            await SayGroup(
                message.websocket,
                message.groupId,
                "梗图{}连发货了喵，请好好享用喵。".format(nums),
            )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断消息是否符合触发条件"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可"), "梗图"]
        )
