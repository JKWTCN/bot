from data.application.application_info import ApplicationInfo
from data.message.message_info import MessageInfo
from abc import ABC, abstractmethod
from data.enumerates import ApplicationType, ApplicationCostType


class Application:
    """
    应用基类
    """

    applicationInfo: ApplicationInfo

    applicationType: ApplicationType

    priority: float
    """触发优先级"""

    isNotEnd: bool
    """是否还能继续触发后面的应用"""

    applicationCostType: ApplicationCostType
    """应用的开销处理"""

    @abstractmethod
    def judge(self, message: MessageInfo) -> bool:
        """判断是否触发应用

        Args:
            message (MessageInfo): 要判断的消息
        """
        # pass

    @abstractmethod
    async def process(self, message: MessageInfo):
        """处理消息

        Args:
            message (Messsage): 要处理的消息
        """
        # pass

    def __init__(
        self,
        applicationInfo: ApplicationInfo,
        priority: float,
        isNotEnd=False,
        applicationCostType=ApplicationCostType.NORMAL,
    ):
        """应用类的构造函数

        Args:
            applicationInfo (ApplicationInfo): 应用信息
            priority (float): 应用触发优先级
            isNotEnd (bool, optional): 是否还能继续触发后面的应用 Defaults to False.
        """
        self.applicationInfo = applicationInfo
        self.priority = priority
        self.isNotEnd = isNotEnd
        self.applicationCostType = applicationCostType
