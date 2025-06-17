from application_info import ApplicationInfo
from data.message.message_info import MessageInfo
from abc import ABC, abstractmethod
from data.application.application_type import ApplicationType


class Application(ABC):
    """
    应用基类
    """

    applicationInfo: ApplicationInfo

    applicationType: ApplicationType

    priority: float
    """触发优先级"""

    isNotEnd: bool
    """是否还能继续触发后面的应用"""

    @abstractmethod
    def process(self, message: MessageInfo):
        """处理消息

        Args:
            message (Messsage): 要处理的消息
        """
        pass

    def __init__(
        self, applicationInfo: ApplicationInfo, priority: float, isNotEnd=False
    ):
        """应用类的构造函数

        Args:
            applicationInfo (ApplicationInfo): 应用信息
            priority (float): 应用触发优先级
            isNotEnd (bool, optional): 是否还能继续触发后面的应用 Defaults to False.
        """
        self.applicationInfo = applicationInfo
        self.priority = priority
