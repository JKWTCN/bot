from enum import Enum


class MessageType(Enum):
    """消息封装类型枚举"""

    GROUP_MESSAGE = 1
    PRIVATE_MESSAGE = 2
    HEART_MESSAGE = 3
    CUSTOMIZE_MESSAGE = 4
    OTHER_MESSAGE = 5
