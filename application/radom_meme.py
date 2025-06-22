import base64
import glob
import json
import logging
from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMesssageInfo
from function.say import SayRaw, SayGroup
from tools.tools import FindNum, load_setting

import random


def FindAllFiles(path: str):
    s = []
    dir_path = "{}/**/*.*".format(path)
    for file in glob.glob(dir_path, recursive=True):
        # print(file)
        s.append(file)
    return s


async def SendMemeMergeForwarding(websocket, group_id: int, nums: int):
    """发送随机梗图合并转发消息"""
    try:
        all_file = FindAllFiles(load_setting()["meme_path"])
        logging.info("读取目录完毕")
        payload = {
            "action": "send_forward_msg",
            "params": {
                "message_type": "group",
                "group_id": group_id,
                "message": [],
            },
        }
        for i in range(nums):
            dir = random.choice(all_file)
            while (
                not dir.endswith(".jpg")
                and not dir.endswith(".png")
                and not dir.endswith(".JPG")
                and not dir.endswith(".JPG")
                and not dir.endswith(".PNG")
                and not dir.endswith(".JEPG")
                and not dir.endswith(".jpeg")
                and not dir.endswith(".gif")
                and not dir.endswith(".GIF")
            ):
                dir = random.choice(all_file)
            print(dir)
            logging.info("剩余发送{}张，发送了图片:{}".format(nums - i - 1, dir))
            with open(dir, "rb") as image_file:
                image_data = image_file.read()
            image_base64 = base64.b64encode(image_data)
            payload["params"]["message"].append(
                {
                    "type": "node",
                    "data": {
                        "user_id": load_setting()["bot_id"],
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


class RadomMemeApplicaiton(GroupMessageApplication):
    def __init__(
        self,
    ):
        applicationInfo = ApplicationInfo("随机梗图功能", "触发:梗图X连")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMesssageInfo):
        num = FindNum(message.painTextMessage)
        import math

        num = math.trunc(num)
        if num > 50:
            await SayGroup(
                message.websocket,
                message.groupId,
                "最大50连喵！",
            )
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

    def judge(self, message: GroupMesssageInfo) -> bool:
        """判断消息是否符合触发条件"""
        if "梗图" in message.painTextMessage and "连" in message.painTextMessage:
            return True
        return False
