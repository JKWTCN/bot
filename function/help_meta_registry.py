"""帮助菜单的应用元数据注册表.

为什么不直接改 60+ 个 ApplicationInfo 构造函数?
- 集中维护一份「触发方式 / 详细说明 / 分类 / 可配置参数」清单,
  避免改动散落在各应用文件里,新增功能时只需在此处补一条.

工作方式:
- help_menu 在渲染菜单/详情前,调用 apply_registry(app) 把这里的元数据
  合并进 app.applicationInfo(仅当 ApplicationInfo 中对应字段为空时填充,
  应用自身显式设置的值优先).
- 以应用名称(name)作为匹配键.

新增功能时:复制一条记录,改 name / trigger / detail / category / params 即可.
"""

from data.application.application_category import AppCategory


# name -> {trigger, detail, category, params}
REGISTRY = {
    # ---- 签到积分 ----
    "签到应用": {
        "trigger": "消息含「签到」且带 bot 名",
        "detail": "每日签到获取积分,一天一次。",
        "category": AppCategory.CHECKIN_POINT,
    },
    "群签到": {
        "trigger": "（定时触发,每日）",
        "detail": "每日定时群签到。",
        "category": AppCategory.CHECKIN_POINT,
    },
    "积分帮助": {
        "trigger": "bot名 + 积分帮助",
        "detail": "说明积分的获取途径:抽奖、签到、水群、大头菜贸易。",
        "category": AppCategory.CHECKIN_POINT,
    },
    "积分抽奖和群低保": {
        "trigger": "bot名 + 抽奖(+ 数字)",
        "detail": "消耗积分参与抽奖,数字为投入积分。",
        "category": AppCategory.CHECKIN_POINT,
    },
    "积分银行": {
        "trigger": "bot名 + 银行 / 存款 / 取款(+ 数字)",
        "detail": "把积分存入银行,每日自动结算利息。",
        "category": AppCategory.CHECKIN_POINT,
    },
    "大头菜贸易": {
        "trigger": "bot名 + 大头菜(+ 买/卖 + 数量)",
        "detail": "低买高卖大头菜赚取积分,价格每日波动。",
        "category": AppCategory.CHECKIN_POINT,
    },
    "跑路或者梭哈": {
        "trigger": "bot名 + 跑路 + 梭哈",
        "detail": "一键梭哈:成功积分翻 10 倍,失败清零甚至被踢。",
        "category": AppCategory.CHECKIN_POINT,
    },

    # ---- 娱乐 ----
    "随机梗图功能": {
        "trigger": "消息含「梗图X连」(如 梗图三连)",
        "detail": "发送指定连数的随机梗图。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "猫猫翻译": {
        "trigger": "bot名 + 翻译(+ 含喵的内容)",
        "detail": "把全是「喵喵」的话翻译回中文。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "艾特随机群友": {
        "trigger": "消息含「随机群友」并 @bot",
        "detail": "随机艾特一个群友。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "漂流瓶应用": {
        "trigger": "bot名 + 捞漂流瓶 / 扔漂流瓶(+ 内容)",
        "detail": "扔一个漂流瓶,或随机捞起一个。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "评论漂流瓶应用": {
        "trigger": "bot名 + 评论漂流瓶(+ 内容)",
        "detail": "对捞到的漂流瓶进行评论。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "随机一言": {
        "trigger": "bot名 + 一言",
        "detail": "获取一条随机一言。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "丢骰子": {
        "trigger": "bot名 + 丢骰子",
        "detail": "随机投掷一颗骰子(1~6)。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "每日运势": {
        "trigger": "bot名 + 运势",
        "detail": "查看今日运势。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "疯狂星期四应用": {
        "trigger": "bot名 + 疯狂星期四 / KFC",
        "detail": "获取一条疯狂星期四文案。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "塔罗牌应用": {
        "trigger": "bot名 + 塔罗牌",
        "detail": "抽一张塔罗牌。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "答案之书应用": {
        "trigger": "bot名 + 答案之书(+ 问题)",
        "detail": "翻一页答案之书,获取一个答案。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "讲冷笑话应用": {
        "trigger": "bot名 + 冷笑话",
        "detail": "讲一个冷笑话。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "卖萌应用": {
        "trigger": "bot名 + 卖萌",
        "detail": "随机卖一个萌。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "抽签": {
        "trigger": "bot名 + 抽签",
        "detail": "抽取一支签。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "今天吃什么": {
        "trigger": "bot名 + 今天吃什么",
        "detail": "随机推荐今天吃什么。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "喜报悲报应用": {
        "trigger": "bot名 + 喜报 / 悲报(+ 内容)",
        "detail": "生成一张喜报或悲报图片。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "午时已到": {
        "trigger": "bot名 + 午时已到",
        "detail": "午时已到,决斗吧。",
        "category": AppCategory.ENTERTAINMENT,
    },

    # ---- 图片 ----
    "随机猫猫": {
        "trigger": "bot名 + 猫猫",
        "detail": "获取一张随机猫猫图片。",
        "category": AppCategory.IMAGE,
    },
    "随机猫猫动图": {
        "trigger": "bot名 + 猫猫动图",
        "detail": "获取一张随机猫猫动图。",
        "category": AppCategory.IMAGE,
    },
    "看世界应用": {
        "trigger": "bot名 + 看世界",
        "detail": "随机看一张世界图片。",
        "category": AppCategory.IMAGE,
    },
    "获取COS图": {
        "trigger": "bot名 + COS",
        "detail": "获取一张随机 COS 图片。",
        "category": AppCategory.IMAGE,
    },
    "二次元应用": {
        "trigger": "bot名 + 二次元 / waifu",
        "detail": "获取一张随机二次元美图。",
        "category": AppCategory.IMAGE,
    },
    "三次元应用": {
        "trigger": "bot名 + 三次元 / realwife",
        "detail": "获取一张随机三次元美图。",
        "category": AppCategory.IMAGE,
    },
    "涩图兑换": {
        "trigger": "bot名 + 涩图(+ 数量)",
        "detail": "消耗积分兑换涩图。",
        "category": AppCategory.IMAGE,
    },
    "随机HTTP猫猫": {
        "trigger": "bot名 + HTTP猫猫(+ 状态码)",
        "detail": "获取对应 HTTP 状态码的猫猫图片。",
        "category": AppCategory.IMAGE,
    },
    "图片镜像": {
        "trigger": "发送图片并带「镜像/对称」等关键词",
        "detail": "对图片做水平镜像或对称处理。",
        "category": AppCategory.IMAGE,
    },

    # ---- 日常 ----
    "每日一言": {
        "trigger": "bot名 + 每日一言",
        "detail": "获取今日每日一言。",
        "category": AppCategory.DAILY,
    },
    "早安应用": {
        "trigger": "消息含「早安/早上好/早」(6~10点)",
        "detail": "早晨打招呼,回复早安图。",
        "category": AppCategory.DAILY,
    },
    "早上好应用": {
        "trigger": "消息含「早上好」",
        "detail": "回复早上好。",
        "category": AppCategory.DAILY,
    },
    "晚安应用": {
        "trigger": "bot名 + 晚安",
        "detail": "回复晚安。",
        "category": AppCategory.DAILY,
    },

    # ---- 统计 ----
    "我的发言图表": {
        "trigger": "bot名 + 发言图表(+ 生涯/本年/本季度/本月/本周)",
        "detail": "查看自己在指定周期内的发言趋势图表。",
        "category": AppCategory.STATISTICS,
    },
    "我的发言热力图": {
        "trigger": "bot名 + 发言热力图(+ 周期)",
        "detail": "查看自己在指定周期内的发言热力分布。",
        "category": AppCategory.STATISTICS,
    },
    "我的发言词云": {
        "trigger": "bot名 + 发言词云(+ 周期)",
        "detail": "查看自己在指定周期内的发言词云。",
        "category": AppCategory.STATISTICS,
    },
    "群发言热力图": {
        "trigger": "bot名 + 群发言热力图(+ 周期)",
        "detail": "查看群组在指定周期内的发言热力分布。",
        "category": AppCategory.STATISTICS,
    },
    "群发言词云": {
        "trigger": "bot名 + 群发言词云(+ 周期)",
        "detail": "查看群组在指定周期内的发言词云。",
        "category": AppCategory.STATISTICS,
    },
    "排名": {
        "trigger": "bot名 + 排名",
        "detail": "查看群内积分 / 发言等排名。",
        "category": AppCategory.STATISTICS,
    },
    "梗图统计": {
        "trigger": "bot名 + 梗图统计",
        "detail": "统计梗图库存情况。",
        "category": AppCategory.STATISTICS,
    },
    "个人统计": {
        "trigger": "bot名 + 个人统计",
        "detail": "查看个人的各项统计。",
        "category": AppCategory.STATISTICS,
    },

    # ---- 实用 ----
    "天气应用": {
        "trigger": "bot名 + 天气(+ 城市名)",
        "detail": "查询指定城市的天气。",
        "category": AppCategory.UTILITY,
    },
    "BiliBili解析": {
        "trigger": "消息含 BiliBili/B站 视频链接",
        "detail": "自动解析并发送 B 站视频信息。",
        "category": AppCategory.UTILITY,
    },
    "必应搜索应用": {
        "trigger": "bot名 + 搜索(+ 关键词)",
        "detail": "使用必应搜索关键词并返回结果。",
        "category": AppCategory.UTILITY,
    },
    "Steam ID 绑定": {
        "trigger": "bot名 + 绑定steam(+ steamID)",
        "detail": "绑定 Steam ID,绑定后可接收状态推送。",
        "category": AppCategory.UTILITY,
    },
    "Steam 状态推送": {
        "trigger": "（定时触发）",
        "detail": "定时检查并推送 Steam 好友状态变化。",
        "category": AppCategory.UTILITY,
    },
    "获取系统状态应用": {
        "trigger": "bot名 + 系统状态(管理员)",
        "detail": "查看机器人所在服务器系统状态。",
        "category": AppCategory.UTILITY,
    },
    "获取IP应用": {
        "trigger": "bot名 + IP(管理员)",
        "detail": "查看本机 IP。",
        "category": AppCategory.UTILITY,
    },
    "获取环境温度": {
        "trigger": "bot名 + 温度",
        "detail": "获取服务器环境温度。",
        "category": AppCategory.UTILITY,
    },
    "ai聊天功能": {
        "trigger": "@bot 或带 bot 名的消息",
        "detail": "AI 根据上下文进行聊天回复。",
        "category": AppCategory.UTILITY,
    },

    # ---- 群管 ----
    "欢迎和入群验证": {
        "trigger": "（新人入群自动触发）",
        "detail": "新人入群时发送欢迎并要求完成验证码验证。",
        "category": AppCategory.GROUP_MANAGE,
    },
    "刷新验证码": {
        "trigger": "（定时触发）",
        "detail": "定时刷新入群验证码。",
        "category": AppCategory.GROUP_MANAGE,
    },
    "敏感词检查": {
        "trigger": "（消息含敏感词自动触发）",
        "detail": "检测到敏感词后撤回并禁言。",
        "category": AppCategory.GROUP_MANAGE,
    },
    "艾特功能大合集": {
        "trigger": "@bot + 相关子指令(管理员)",
        "detail": "艾特相关的群管理功能集合。",
        "category": AppCategory.GROUP_MANAGE,
    },
    "艾特惩罚": {
        "trigger": "（艾特行为自动触发）",
        "detail": "对艾特行为施加惩罚。",
        "category": AppCategory.GROUP_MANAGE,
    },
    "打响指应用": {
        "trigger": "bot名 + 打响指",
        "detail": "灭霸响指,清除一半群员(玩梗)。",
        "category": AppCategory.GROUP_MANAGE,
    },
    "再也不见": {
        "trigger": "bot名 + 再也不见 / 自助退群",
        "detail": "发送后自助退群。",
        "category": AppCategory.GROUP_MANAGE,
    },
    "复读": {
        "trigger": "（随机触发）",
        "detail": "随机复读群友的话。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "复读机": {
        "trigger": "（检测到复读机行为自动触发）",
        "detail": "检测群友的复读机行为。",
        "category": AppCategory.ENTERTAINMENT,
    },
    "无聊功能触发合集": {
        "trigger": "（无聊功能自动触发）",
        "detail": "无聊功能集合。",
        "category": AppCategory.ENTERTAINMENT,
    },
}


def apply_registry(app):
    """把注册表中的元数据合并进 app.applicationInfo.

    仅当应用自身未显式设置(字段为空 / 为默认分类)时才填充,
    保证应用自带的值优先。
    """
    info = app.applicationInfo
    meta = REGISTRY.get(info.name)
    if not meta:
        return info
    if not getattr(info, "trigger", ""):
        info.trigger = meta.get("trigger", "")
    if not getattr(info, "detail", ""):
        info.detail = meta.get("detail", "")
    cat = meta.get("category")
    if cat and (not getattr(info, "category", None) or info.category == AppCategory.OTHER):
        info.category = cat
    params = meta.get("params")
    if params and not getattr(info, "params", None):
        info.params = list(params)
    return info
