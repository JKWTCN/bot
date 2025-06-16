from enum import Enum


class MessagePostType(Enum):
    MESSAGE = 1
    NOTICE = 2
    REQUEST = 3
    META_EVENT = 4
    UNKONW_EVENT = 5

    def string2MessagePostType(messagePostTypeString: str):
        match messagePostTypeString:
            case "message":
                return MessagePostType.MESSAGE
            case "notice":
                return MessagePostType.NOTICE
            case "request":
                return MessagePostType.REQUEST
            case "meta_event":
                return MessagePostType.META_EVENT
            case _:
                raise MessagePostType.UNKONW_EVENT
