from data.application.application import Application
from data.message.private_message_info import PrivateMesssageInfo
from data.enumerates import ApplicationType, ApplicationCostType

from abc import ABC, abstractmethod


class PrivateMessageApplication(Application):
    """群消息应用类"""

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
        self.applicationType = ApplicationType.PRIVATE_MESSAGE

    @abstractmethod
    def process(self, message: PrivateMesssageInfo):
        """处理消息

        Args:
            message (GroupMesssageInfo): 要处理的消息
        """
        pass
