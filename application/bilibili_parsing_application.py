import json
import logging

import requests
from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMesssageInfo
from function.say import SayRaw, ReplySay
from function.GroupConfig import get_config
import random


class BiliBiliParsingApplication(GroupMessageApplication):
    def __init__(
        self,
    ):
        applicationInfo = ApplicationInfo("BiliBili解析", "解析BiliBili视频链接")
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMesssageInfo):
        for k in message.rawMessage["message"]:
            if k["type"] == "json":
                # qq卡片消息解析
                now_json = json.loads(k["data"]["data"])
                if "meta" in now_json:
                    if "detail_1" in now_json["meta"]:
                        if "qqdocurl" in now_json["meta"]["detail_1"]:
                            qqdocurl = now_json["meta"]["detail_1"]["qqdocurl"]
                            r = requests.get(qqdocurl)
                            no_get_params_url = r.url.split("?")[0]
                            logging.info(f"解析结果:{no_get_params_url}")
                            await ReplySay(
                                message.websocket,
                                message.groupId,
                                message.messageId,
                                no_get_params_url,
                            )

    def judge(self, message: GroupMesssageInfo) -> bool:
        return get_config("bilibili_parsing", group_id)  # type: ignore
