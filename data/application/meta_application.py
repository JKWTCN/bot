from data.application.application import Application
from data.message.meta_message_info import MetaMessageInfo
from data.enumerates import ApplicationType, ApplicationCostType

from abc import ABC, abstractmethod


class MetaMessageApplication(Application):
    """通知消息应用类"""

    def __init__(
        self,
        applicationInfo,
        priority: float,
        isNotEnd=False,
        applicationCostType=ApplicationCostType.NORMAL,
    ):
        """群消息事件类的构造函数

        Args:
            applicationInfo (ApplicationInfo): 应用信息
            priority (float): 应用触发优先级
            isNotEnd (bool, optional): 是否还能继续触发后面的应用 Defaults to False.
        """
        super().__init__(applicationInfo, priority, isNotEnd, applicationCostType)
        self.applicationType = ApplicationType.META

    @abstractmethod
    def process(self, message: MetaMessageInfo):
        """处理消息

        Args:
            message (GroupMesssageInfo): 要处理的消息
        """
        pass
