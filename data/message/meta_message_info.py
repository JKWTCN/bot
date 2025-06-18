from data.enumerates import MessageType, MetaEventType
from data.message.message_info import MessageInfo


class MetaMessageInfo(MessageInfo):
    senderId: int
    messageId: int
    metaEventType: MetaEventType

    def __init__(self, websocket, rawMessage: dict):
        super().__init__(websocket, rawMessage)
        self.messageType = MessageType.META
        match rawMessage["meta_event_type"]:
            case "lifecycle":
                match rawMessage["sub_type"]:
                    case "enable":
                        self.metaEventType = MetaEventType.ENABLE
                    case "disable":
                        self.metaEventType = MetaEventType.DISABLE
                    case "connect":
                        self.metaEventType = MetaEventType.CONNECT
                    case _:
                        self.metaEventType = MetaEventType.UNKNOW
            case "heartbeat":
                self.metaEventType = MetaEventType.HEART_BEAT
            case _:
                self.metaEventType = MetaEventType.UNKNOW
