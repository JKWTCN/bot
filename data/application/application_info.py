class ApplicationInfo:
    """应用信息"""

    name: str
    """应用名称"""
    info: str
    """应用功能说明"""

    def __init__(self, name: str, info: str) -> None:
        self.name = name
        self.info = info
        pass
