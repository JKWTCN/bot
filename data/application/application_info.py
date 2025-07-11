class ApplicationInfo:
    """应用信息"""

    name: str
    """应用名称"""
    info: str
    """应用功能说明"""
    can_display = True

    def __init__(self, name: str, info: str, can_display=True) -> None:
        self.name = name
        self.info = info
        self.can_display = can_display
        pass
