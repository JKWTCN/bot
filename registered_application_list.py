import application.hate_at_application
import application.miao_miao_translation
from application.sample_group_message_application import SampleGroupMessageApplication
from application.re_read import ReReadApplication
from schedule.register import RegisterApplication
from application.chat_application import GroupChatApplication
from application.radom_meme import RadomMemeApplication
import application


def initApplications():
    """初始化应用"""
    # RegisterApplication(SampleGroupMessageApplication())
    RegisterApplication(ReReadApplication())
    RegisterApplication(GroupChatApplication())
    RegisterApplication(RadomMemeApplication())
    RegisterApplication(
        application.miao_miao_translation.MiaoMiaoTranslationApplication()
    )
    RegisterApplication(application.hate_at_application.HateAtApplication())
