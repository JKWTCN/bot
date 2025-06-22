from enum import Enum


class MetaEventType(Enum):
    """meta事件封装类型枚举"""

    ENABLE = 0
    DISABLE = 1
    CONNECT = 2
    HEART_BEAT = 3
    UNKNOW = 4


class MessageType(Enum):
    """消息封装类型枚举"""

    GROUP_MESSAGE = 0
    PRIVATE_MESSAGE = 1
    NOTICE = 2
    REQUEST = 3
    META = 4
    OTHER = 5


class ApplicationType(Enum):
    """应用类型封装枚举"""

    GROUP_MESSAGE = 0
    PRIVATE_MESSAGE = 1
    NOTICE = 2
    REQUEST = 3
    META = 4
    OTHER = 5


class UserType(Enum):
    """用户类型封装枚举"""

    NORMAL = 0
    ADMIN = 1
    OWNER = 2
    DEVELOPER = 3


class NoticeType(Enum):
    """通知类型封装枚举"""

    GROUP_FILE_UPLOAD = 0
    GROUP_ADMIN_CHANGE = 1
    GROUP_MEMBER_DELETE = 2
    GROUP_MEMBER_ADD = 3
    GROUP_BAN_CHAT = 4
    FRIEND_ADD = 5
    GROUP_MESSAGE_RECALL = 6
    FRIEND_MESSAGE_RECALL = 7
    GROUP_POKE = 8
    GROUP_LUCK_DOG = 9
    GROUP_HONOR_CHANGE = 10

    UNKNOW = 11


class RequestEventType(Enum):
    """请求事件枚举封装"""

    FRIEND_ADD = 0
    GROUP_INVITE = 1
    GROUP_ADD = 2

    UNKNOW = 3


class ApplicationCostType(Enum):
    """应用处理时间类型枚举"""

    HIGH_TIME_HIGH_PERFORMANCE = 0
    """高耗时高性能,采用队列处理,比如AI"""

    HIGH_TIME_LOW_PERFORMANCE = 1
    """高耗时低性能,采用并发处理,比如HTTP请求"""

    NORMAL = 2
    """普通应用,主线程处理"""
