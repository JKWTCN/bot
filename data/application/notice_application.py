from data.application.application import Application
from data.message.notice_message_info import NoticeMessageInfo
from data.enumerates import ApplicationType

from abc import ABC, abstractmethod


class NoticeMessageApplication(Application):
    """通知消息应用类"""

    def __init__(self, applicationInfo, priority: float, isNotEnd=False):
        """群消息事件类的构造函数

        Args:
            applicationInfo (ApplicationInfo): 应用信息
            priority (float): 应用触发优先级
            isNotEnd (bool, optional): 是否还能继续触发后面的应用 Defaults to False.
        """
        super().__init__(applicationInfo, priority, isNotEnd)
        self.applicationType = ApplicationType.NOTICE

    @abstractmethod
    def process(self, message: NoticeMessageInfo):
        """处理消息

        Args:
            message (GroupMesssageInfo): 要处理的消息
        """
        pass
