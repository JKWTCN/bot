from data.application.application import Application
from data.message.group_message_info import GroupMesssageInfo
from data.application.application_type import ApplicationType

from abc import ABC, abstractmethod


class OtherApplication(Application):
    """其他事件应用"""

    def __init__(self, applicationInfo, priority: float, isNotEnd=False):
        """群at事件应用类的构造函数

        Args:
            applicationInfo (ApplicationInfo): 应用信息
            priority (float): 应用触发优先级
            isNotEnd (bool, optional): 是否还能继续触发后面的应用 Defaults to False.
        """
        super().__init__(applicationInfo, priority, isNotEnd)
        self.applicationType = ApplicationType.GROUP_AT

    @abstractmethod
    def process(self, message: GroupMesssageInfo):
        """处理消息

        Args:
            message (GroupMesssageInfo): 要处理的消息
        """
        pass
