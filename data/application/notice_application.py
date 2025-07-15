from data.application.application import Application
from data.message.notice_message_info import NoticeMessageInfo
from data.enumerates import ApplicationType, ApplicationCostType

from abc import ABC, abstractmethod


class NoticeMessageApplication(Application):
    """通知消息应用类"""

    def __init__(
        self,
        applicationInfo,
        priority: float,
        canContinue=False,
        applicationCostType=ApplicationCostType.NORMAL,
    ):
        """群消息事件类的构造函数

        Args:
            applicationInfo (ApplicationInfo): 应用信息
            priority (float): 应用触发优先级
            canContinue (bool, optional): 是否还能继续触发后面的应用 Defaults to False.
        """
        super().__init__(applicationInfo, priority, canContinue, applicationCostType)
        self.applicationType = ApplicationType.NOTICE

    @abstractmethod
    def process(self, message: NoticeMessageInfo):
        """处理消息

        Args:
            message (GroupMessageInfo): 要处理的消息
        """

    @abstractmethod
    def judge(self, message: NoticeMessageInfo) -> bool:
        """判断是否触发应用

        Args:
            message (MessageInfo): 要判断的消息
        """
