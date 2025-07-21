import os
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
import application.cold_group_king as cold_group_king


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
    # 注册大清洗应用
    RegisterApplication(classic_application.GreatPurgeApplication())
    # 随机派发水群积分应用
    RegisterApplication(classic_application.RandomWaterGroupPointsApplication())
    # 注册无聊功能
    RegisterApplication(classic_application.BoringFeatureCollectionManageApplication())
    RegisterApplication(classic_application.BoringFeatureCollectionApplication())
    RegisterApplication(classic_application.AtPunishApplication())
    # 注册被欺负应用
    RegisterApplication(classic_application.BeTeasedApplication())
    # 注册冷群王应用
    RegisterApplication(cold_group_king.ColdGroupKingChatApplication())
    RegisterApplication(cold_group_king.ColdGroupKingRefreshStatusApplication())
    # 注册艾特管理功能大合集
    RegisterApplication(classic_application.AtManagementApplication())
    # 注册漂流瓶应用
    RegisterApplication(classic_application.DriftBottleApplication())
    RegisterApplication(classic_application.CommentDriftBottleApplication())
    # 注册管理开发者特色回复应用
    RegisterApplication(classic_application.SpicalReplyApplication())
    # 注册加精/移除加精应用
    RegisterApplication(classic_application.EssenceAboutGroupMessageApplication())
    # 注册你们看到她了吗应用
    RegisterApplication(classic_application.WhoLookYouApplication())
    # 注册香香软软小南梁群友应用
    RegisterApplication(classic_application.GroupKotomitakoApplication())
    # 注册猫娘群友应用
    RegisterApplication(classic_application.GroupMiaoMiaoApplication())
    # 注册喵喵日应用
    RegisterApplication(classic_application.GroupMiaoMiaoDayApplication())
    # 注册回文应用
    RegisterApplication(classic_application.LeKeNotKeleApplication())
    # 注册早安应用
    RegisterApplication(classic_application.GoodMorningApplication())
    # 注册功能菜单应用
    RegisterApplication(classic_application.FeaturesMenuApplication())
    # 注册每日一言应用
    RegisterApplication(classic_application.EveryDayOnePassageApplication())
    # 注册黑名单查询应用
    RegisterApplication(classic_application.BlacklistQueryApplication())
    # 注册今天吃什么应用
    RegisterApplication(classic_application.TodayEatWhatApplication())
    # 注册群友的恶趣味功能
    RegisterApplication(classic_application.GroupFriendBadTasteApplication())
    # 注册大头菜应用
    RegisterApplication(classic_application.KohlrabiApplication())
    # 注册午时已到应用
    RegisterApplication(classic_application.LunchTimeApplication())
    # 注册梗图统计应用
    RegisterApplication(classic_application.MemeStatisticsApplication())
    # 群友个人统计应用
    RegisterApplication(classic_application.RankingApplication())
    # 抽签
    RegisterApplication(classic_application.DrawLotteryApplication())
    # 积分帮助
    RegisterApplication(classic_application.PointHelpApplication())
    # 梭哈或者跑路
    RegisterApplication(classic_application.RunOrShotApplication())
    # 反击应用
    RegisterApplication(classic_application.DefenseApplication())
    # 睡眠套餐应用
    RegisterApplication(classic_application.IWantToSleepApplication())
    # 涩图兑换
    RegisterApplication(classic_application.SexImageApplication())
    # 丢骰子
    RegisterApplication(classic_application.GetRadomNum1to6Application())
    # COS图
    RegisterApplication(classic_application.GetCosImageApplication())
    # 自助退群应用
    RegisterApplication(classic_application.SeeYouAgain())
    # 二次元美图应用
    RegisterApplication(classic_application.GetWaiFuApplication())
    # 三次元美图应用
    RegisterApplication(classic_application.GetRealWifeApplication())
    # 随机一言应用
    RegisterApplication(classic_application.RadomOneWordApplication())
    # 随机HTTP猫猫
    RegisterApplication(classic_application.RadomHttpCatApplication())
    # 运势应用
    RegisterApplication(classic_application.LuckDogApplication())
    # 疯狂星期四应用
    RegisterApplication(classic_application.KFCVME50Application())
    # 塔罗牌应用
    RegisterApplication(classic_application.TarotApplication())
    # 晚安应用
    RegisterApplication(classic_application.GoodNightApplication())
    # 随机猫猫
    RegisterApplication(classic_application.RandomCatApplication())
    # 随机猫猫动图
    RegisterApplication(classic_application.RandomCatGifApplication())
    # 看世界应用
    RegisterApplication(classic_application.LookWorldApplication())
    # 紫薯精应用
    RegisterApplication(classic_application.TimelyCheckTanosApplication())
    RegisterApplication(classic_application.ThanosApplication())
    # 环境温度应用
    RegisterApplication(classic_application.GetTemperatureApplication())
    # 早上好应用
    RegisterApplication(classic_application.OldGoodMorningApplication())
    # 喜报悲报应用
    RegisterApplication(classic_application.HappySadNewsApplication())
    # 答案之书应用
    RegisterApplication(classic_application.AnswerBookApplication())
    # 获取系统状态应用
    RegisterApplication(classic_application.GetSystemStatusApplication())
    # 获取本机IP
    RegisterApplication(classic_application.GetSystemIPApplication())
    # 讲冷笑话应用
    RegisterApplication(classic_application.JokeApplication())
    # 卖萌应用
    RegisterApplication(classic_application.CuteApplication())

    # 私聊聊天功能
    RegisterApplication(classic_application.PrivateChatApplication())
    # 偷偷加积分应用
    RegisterApplication(classic_application.StealthyPointsApplication())
    # 发送日志应用
    RegisterApplication(classic_application.SendLogApplication())

    # 拍一拍卖萌应用
    RegisterApplication(classic_application.PokeCuteApplication())
    # 有人离开应用
    RegisterApplication(classic_application.GroupMemberDecreaseApplication())
    # 随机卖萌应用
    RegisterApplication(classic_application.RandomCuteApplication())

    from application.point_application import PointApplication

    # 注册积分抽奖应用
    RegisterApplication(PointApplication())

    from application.debug_application import DebugApplication

    # 注册调试应用
    RegisterApplication(DebugApplication())

    if os.path.exists("private_application/private_application.py"):
        from private_application.private_application import initPrivateApplication

        initPrivateApplication()

    # 注册#命令
    from application.hash_command_application import HashCommandApplication

    RegisterApplication(HashCommandApplication())
