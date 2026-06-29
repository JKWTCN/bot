class ApplicationInfo:
    """应用信息

    帮助菜单等展示功能会读取以下字段:
    - name:        应用名称
    - info:        一句话功能说明
    - trigger:     触发方式描述,例如 "乐可 + 签到" / "发送『可乐』"
    - detail:      详细说明 / 用法示例,查看单功能详情时展示
    - category:    分类标签,用于帮助菜单分组(见 application_category.py)
    - params:      该应用可被群管自定义的 GroupConfig 参数名列表,
                   详情页会读取其当前值并提示如何修改
    - can_display: 是否在帮助菜单中展示
    """

    name: str
    """应用名称"""
    info: str
    """应用功能说明"""
    trigger: str
    """应用触发方式说明"""
    detail: str
    """应用详细说明 / 用法示例"""
    category: str
    """应用所属分类"""
    params: list
    """该应用可自定义的 GroupConfig 参数名列表"""
    can_display = True

    def __init__(
        self,
        name: str,
        info: str,
        can_display=True,
        trigger: str = "",
        detail: str = "",
        category: str = "其他",
        params: list = None,
    ) -> None:
        self.name = name
        self.info = info
        self.can_display = can_display
        self.trigger = trigger
        self.detail = detail
        self.category = category
        # 避免可变默认参数共享,默认给空列表
        self.params = list(params) if params else []
