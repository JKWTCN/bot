import application.GroupConfigApplication
import application.bilibili_parsing_application
import application.carrot_market_application
import application.chat_application
import application.hate_at_application
import application.miao_miao_translation
import application.radom_meme
import application.re_read
import application.sensitive_words_application
from schedule.register import RegisterApplication
import application


def initApplications():
    """初始化应用"""
    # RegisterApplication(SampleGroupMessageApplication())
    RegisterApplication(application.re_read.ReReadApplication())
    RegisterApplication(application.chat_application.GroupChatApplication())
    RegisterApplication(application.radom_meme.RadomMemeApplication())
    RegisterApplication(
        application.miao_miao_translation.MiaoMiaoTranslationApplication()
    )
    RegisterApplication(application.hate_at_application.HateAtApplication())
    RegisterApplication(application.carrot_market_application.CarrotMarketApplication())
    RegisterApplication(application.GroupConfigApplication.GroupConfigApplication())
    RegisterApplication(
        application.sensitive_words_application.SensitiveWordsApplication()
    )
    RegisterApplication(
        application.bilibili_parsing_application.BiliBiliParsingApplication()
    )
