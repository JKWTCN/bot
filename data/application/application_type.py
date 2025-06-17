from enum import Enum


class ApplicationType(Enum):
    GROUP_KEY_WORD = 0
    """群关键词"""
    GROUP_AT = 1
    """群艾特"""
    GROUP_REPLY = 2
    """群引用回复"""
    GROUP_TIME = 3
    """群定时"""
    GROUP_PICK = 4
    """群内戳一戳"""
    PRIVATE_KEY_WORD = 5
    """私聊关键词"""
    PRIVATE_REPLY = 6
    """私聊引用回复"""
    PRIVATE_TIME = 7
    """私聊定时"""
    PRIVATE_PICK = 8
    """私聊戳一戳"""

    GROUP_FILE_UPLOAD = 9
    """群文件上传"""
    GROUP_ADMIN_CHANGE = 10
    """群管理员变动"""
    GROUP_MEMBER_ADD = 11
    """群成员增加"""
    GROUP_MEMBER_DELETE = 12
    """群成员减少"""
    GROUP_NO_CHAT = 13
    """群禁言"""

    FRINEND_ADD = 14
    """好友添加"""
    GROUP_MESSAGE_DELETE = 15
    """群消息撤回"""
    FRINEND_MESSAGE_DELETE = 16
    """好友消息撤回"""
    GROUP_LUCK_DOG = 17
    """群红包运气王"""
    GROUP_HONOR_CHANGE = 18
    """群成员荣誉变更"""
