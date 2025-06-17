from data.application.application import Application
from data.message.group_message_info import GroupMesssageInfo
from data.application.application_type import ApplicationType

from abc import ABC, abstractmethod


class GroupKeyWordApplication(Application):
    """群关键字应用类
    该类用于处理群消息中的关键字匹配功能.
    该类继承自Application基类,并实现了处理群消息的抽象方法.
    该类包含一个静态变量wordAllHasList,用于存储所有已注册的关键字列表.
    该类的构造函数接受应用信息和注册信息作为参数,并设置应用类型为GROUP_KEY_WORD.
    该类的process方法是一个抽象方法,子类需要实现该方法来处理具体的消息.
    """

    wordAllHasList: list[str] = []
    """全部有则匹配"""
    wordAnyHasList: list[str] = []
    """有一个则匹配"""
    wordAnyNotHasList: list[str] = []
    """有一个就不匹配"""
    wordNotTogetherList: list[str] = []
    """不同时则匹配"""
    wordMustTogetherList: list[str] = []
    """同时出现则匹配"""

    def __init__(self, applicationInfo, priority: float, isNotEnd=False):
        """群关键词事件应用类的构造函数

        Args:
            applicationInfo (ApplicationInfo): 应用信息
            priority (float): 应用触发优先级
            isNotEnd (bool, optional): 是否还能继续触发后面的应用 Defaults to False.
        """
        super().__init__(applicationInfo, priority, isNotEnd)
        self.applicationType = ApplicationType.GROUP_KEY_WORD

    @abstractmethod
    def process(self, message: GroupMesssageInfo):
        """处理消息

        Args:
            message (GroupMesssageInfo): 要处理的消息
        """
        pass
