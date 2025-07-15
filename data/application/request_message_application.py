from data.application.application import Application
from data.message.request_message_info import RequestMessageInfo
from data.enumerates import ApplicationType, ApplicationCostType

from abc import ABC, abstractmethod


class RequestMessageApplication(Application):
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
        self.applicationType = ApplicationType.REQUEST

    @abstractmethod
    def process(self, message: RequestMessageInfo):
        """处理消息

        Args:
            message (RequestMessageInfo): 要处理的消息
        """
        pass

    @abstractmethod
    def judge(self, message: RequestMessageInfo) -> bool:
        """判断是否触发应用

        Args:
            message (MessageInfo): 要判断的消息
        """
