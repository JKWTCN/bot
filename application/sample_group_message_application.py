from data.message.group_message_info import GroupMesssageInfo
from data.application.application_info import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from schedule.register import RegisterApplication
from data.enumerates import ApplicationCostType

from function.say import say

class SampleGroupMessageApplication(GroupMessageApplication):
    """
    此为群关键词应用的示例应用
    触发关键词为123
    """

    async def process(self, message: GroupMesssageInfo):
        """处理消息

        Args:
            message (MessageInfo): 要处理的消息
        """
        await say(message.websocket, message.groupId, "触发了关键词应用123")
        pass

    def judge(self, message: GroupMesssageInfo) -> bool:
        """判断是否成立

        Args:
            message (MessageInfo): 传入消息

        Returns:
            bool: 判断结果
        """
        if "123" in message.painTextMessage:
            print(f"触发了关键词应用123,消息内容:{message.painTextMessage}")
            return True
        return False

    def __init__(self):
        applicationInfo = ApplicationInfo("测试应用", "测试功能")
        # super().__init__(applicationInfo, 2.0, False, ApplicationCostType.HIGH_TIME_HIGH_PERFORMANCE)
        # super().__init__(applicationInfo, 2.0, False, ApplicationCostType.HIGH_TIME_LOW_PERFORMANCE)
        super().__init__(applicationInfo, 2.0, False, ApplicationCostType.NORMAL)


RegisterApplication(SampleGroupMessageApplication())
