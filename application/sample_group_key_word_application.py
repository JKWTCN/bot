from data.application.group_key_word_application import GroupKeyWordApplication
from data.message.group_message_info import GroupMesssageInfo
from data.message.message_info import MessageInfo
from data.register.register import RegisterAppliaction
from data.application.application_info import ApplicationInfo


class SampleGroupKeyWordApplication(GroupKeyWordApplication):
    """
    此为群关键词应用的示例应用
    触发关键词为123
    """

    def process(self, message: GroupMesssageInfo):
        """处理消息

        Args:
            message (MessageInfo): 要处理的消息
        """
        pass

    def judge(self, message: MessageInfo) -> bool:
        """判断是否成立

        Args:
            message (MessageInfo): 传入消息

        Returns:
            bool: 判断结果
        """
        return True

    def __init__(self):
        applicationInfo = ApplicationInfo("测试应用", "测试功能")
        super().__init__(applicationInfo, 2.0)
        self.wordAllHasList = ["123"]


RegisterAppliaction(SampleGroupKeyWordApplication())
