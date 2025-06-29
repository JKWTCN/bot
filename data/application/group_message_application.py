from data.application.application import Application
from data.message.group_message_info import GroupMessageInfo
from data.enumerates import ApplicationType, ApplicationCostType

from abc import ABC, abstractmethod


class GroupMessageApplication(Application):
    """群关键字应用类
    该类用于处理群消息中的关键字匹配功能.
    该类继承自Application基类,并实现了处理群消息的抽象方法.
    该类包含一个静态变量wordAllHasList,用于存储所有已注册的关键字列表.
    该类的构造函数接受应用信息和注册信息作为参数,并设置应用类型为GROUP_KEY_WORD.
    该类的process方法是一个抽象方法,子类需要实现该方法来处理具体的消息.
    """

    def __init__(
        self,
        applicationInfo,
        priority: float,
        canContinue=False,
        applicationCostType=ApplicationCostType.NORMAL,
    ):
        """群关键词事件应用类的构造函数

        Args:
            applicationInfo (ApplicationInfo): 应用信息
            priority (float): 应用触发优先级
            canContinue (bool, optional): 是否还能继续触发后面的应用 Defaults to False.
        """
        super().__init__(applicationInfo, priority, canContinue, applicationCostType)
        self.applicationType = ApplicationType.GROUP_MESSAGE

    # @abstractmethod
    # def process(self, message: GroupMessageInfo):
    #     """处理消息

    #     Args:
    #         message (GroupMessageInfo): 要处理的消息
    #     """
    #     pass
    @abstractmethod
    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用

        Args:
            message (MessageInfo): 要判断的消息
        """
        # pass

    @abstractmethod
    async def process(self, message: GroupMessageInfo):
        """处理消息

        Args:
            message (Messsage): 要处理的消息
        """
        # pass
