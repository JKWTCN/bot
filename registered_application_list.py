import application.GroupConfigApplication
import application.bilibili_parsing_application
import application.carrot_market_application
import application.chat_application
import application.hate_at_application
import application.miao_miao_translation
import application.radom_meme
import application.re_read
import application.sensitive_words_application
import application.welcome_application
from schedule.register import RegisterApplication
import application
import application.classic_application as classic_application


def initApplications():
    """初始化应用"""
    # RegisterApplication(SampleGroupMessageApplication())
    # 注册复读应用
    RegisterApplication(application.re_read.ReReadApplication())
    # 注册聊天应用
    RegisterApplication(application.chat_application.GroupChatApplication())
    # 注册随机meme应用
    RegisterApplication(application.radom_meme.RadomMemeApplication())
    # 注册喵喵翻译应用
    RegisterApplication(
        application.miao_miao_translation.MiaoMiaoTranslationApplication()
    )
    # 注册讨厌艾特应用
    RegisterApplication(application.hate_at_application.HateAtApplication())
    # 注册胡萝卜市场应用
    RegisterApplication(application.carrot_market_application.CarrotMarketApplication())
    # 注册群设置应用
    RegisterApplication(application.GroupConfigApplication.GroupConfigApplication())
    # 注册敏感词应用
    RegisterApplication(
        application.sensitive_words_application.SensitiveWordsApplication()
    )
    # 注册B站解析应用
    RegisterApplication(
        application.bilibili_parsing_application.BiliBiliParsingApplication()
    )
    # 入群验证
    RegisterApplication(application.welcome_application.WelcomeApplication())
    RegisterApplication(application.welcome_application.VerifyApplication())
    RegisterApplication(application.welcome_application.RefreshVcodeApplication())
    RegisterApplication(application.welcome_application.ManualVerifyApplication())
    # 注册签到应用
    RegisterApplication(classic_application.CheckInApplication())
