"""应用分类常量

帮助菜单按这些分类对应用进行分组展示.
应用在 ApplicationInfo 中通过 category 字段引用这里的常量.
"""


class AppCategory:
    """应用分类常量集合"""

    CHECKIN_POINT = "签到积分"
    """签到、积分、银行、抽奖等"""

    ENTERTAINMENT = "娱乐"
    """玩梗、随机一言、塔罗、运势等趣味功能"""

    IMAGE = "图片"
    """猫猫、涩图、二次元/三次元美图、HTTP猫猫等图片类"""

    STATISTICS = "统计"
    """发言图表、热力图、词云、排名等数据统计"""

    GROUP_MANAGE = "群管"
    """入群验证、敏感词、加精、艾特管理、踢人等群管理"""

    UTILITY = "实用"
    """天气、搜索、B站解析、Steam状态、系统状态等实用工具"""

    DAILY = "日常"
    """早安/晚安、每日一言、今天吃什么等每日定时/问候功能"""

    OTHER = "其他"
    """未明确分类的应用"""

    # 帮助菜单中分类的展示顺序
    DISPLAY_ORDER = [
        CHECKIN_POINT,
        ENTERTAINMENT,
        IMAGE,
        DAILY,
        STATISTICS,
        UTILITY,
        GROUP_MANAGE,
        OTHER,
    ]

    @classmethod
    def all_categories(cls) -> list:
        """返回所有分类(按展示顺序)"""
        return list(cls.DISPLAY_ORDER)

    @classmethod
    def find_by_keyword(cls, keyword: str):
        """根据关键词(模糊匹配,如 '图片'/'娱乐')返回对应分类名,
        匹配不到则返回 None."""
        if not keyword:
            return None
        for category in cls.DISPLAY_ORDER:
            if keyword == category or keyword in category or category in keyword:
                return category
        return None
