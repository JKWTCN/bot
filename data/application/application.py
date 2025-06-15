from application_info import ApplicationInfo
from data.register.register_info import RegisterInfo
from data.message import Messsage


class Application:
    """
    应用类
    """

    applicationInfo: ApplicationInfo

    registerInfo: RegisterInfo

    def process(self, message: Messsage):
        """处理消息

        Args:
            message (Messsage): 要处理的消息
        """
        pass

    def __init__(self, applicationInfo: ApplicationInfo, registerInfo: RegisterInfo):
        """应用类的构造函数

        Args:
            applicationInfo (ApplicationInfo): 应用信息
            registerInfo (RegisterInfo): 注册信息
        """
        self.applicationInfo = applicationInfo
        self.registerInfo = registerInfo
        self.applicationInfo.application = self
