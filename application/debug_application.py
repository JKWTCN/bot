import logging
from data.message.group_message_info import GroupMessageInfo
from data.application.application_info import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from tools.tools import load_setting, dump_setting, HasAllKeyWords
from function.datebase_user import IsDeveloper
from function.say import SayGroup


class DebugApplication(GroupMessageApplication):
    def __init__(self):
        super().__init__(
            ApplicationInfo(
                name="Debug模式开关",
                info="Debug模式开关,用于指定日志输出级别方便调试和测试",
            ),
            50,
        )

    async def process(self, message: GroupMessageInfo):
        if not load_setting("debug_mode", False):
            dump_setting("debug_mode", True)
            if not load_setting("debug_mode", False):
                print("Debug模式已开启")
            else:
                logging.info("Debug模式已开启")
            await SayGroup(
                message.websocket,
                message.groupId,
                "Debug模式已开启喵。",
            )
        else:
            dump_setting("debug_mode", False)
            if not load_setting("debug_mode", False):
                print("Debug模式已关闭")
            else:
                logging.info("Debug模式已关闭")
            await SayGroup(
                message.websocket,
                message.groupId,
                "Debug模式已经关闭喵。",
            )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return IsDeveloper(message.senderId) and HasAllKeyWords(
            message.plainTextMessage, ["debug", load_setting("bot_name", "乐可")]
        )
