import application.miao_miao_translation
from application.sample_group_message_application import SampleGroupMessageApplication
from application.re_read import ReReadApplicaiton
from schedule.register import RegisterApplication
from application.chat_application import GroupChatApplicaiton
from application.radom_meme import RadomMemeApplicaiton
import application


def initApplications():
    """初始化应用"""
    # RegisterApplication(SampleGroupMessageApplication())
    RegisterApplication(ReReadApplicaiton())
    RegisterApplication(GroupChatApplicaiton())
    RegisterApplication(RadomMemeApplicaiton())
    RegisterApplication(
        application.miao_miao_translation.MiaoMiaoTranslationApplicaiton()
    )
