from data.application.application import Application
from data.message.group_message_info import GroupMessageInfo
from data.enumerates import ApplicationType, ApplicationCostType

from abc import ABC, abstractmethod


class OtherApplication(Application):
    """其他事件应用"""

    def __init__(
        self,
        applicationInfo,
        priority: float,
        canContinue=False,
        applicationCostType=ApplicationCostType.NORMAL,
    ):
        """群at事件应用类的构造函数

        Args:
            applicationInfo (ApplicationInfo): 应用信息
            priority (float): 应用触发优先级
            canContinue (bool, optional): 是否还能继续触发后面的应用 Defaults to False.
        """
        super().__init__(applicationInfo, priority, canContinue, applicationCostType)
        self.applicationType = ApplicationType.OTHER

    @abstractmethod
    def process(self, message: GroupMessageInfo):
        """处理消息

        Args:
            message (GroupMessageInfo): 要处理的消息
        """
        pass

    @abstractmethod
    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用

        Args:
            message (MessageInfo): 要判断的消息
        """
