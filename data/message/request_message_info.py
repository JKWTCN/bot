from data.enumerates import MessageType, RequestEventType
from data.message.message_info import MessageInfo


class RequestMessageInfo(MessageInfo):

    def __init__(self, websocket, rawMessage: dict):
        self.senderId: int
        self.messageId: int
        self.requestEventType: RequestEventType
        super().__init__(websocket, rawMessage)
        self.messageType = MessageType.REQUEST
        match rawMessage["request_type"]:
            case "friend":
                self.requestEventType = RequestEventType.FRIEND_ADD

            case "group":
                match rawMessage["sub_type"]:
                    case "add":
                        self.requestEventType = RequestEventType.GROUP_ADD
                    case "invite":
                        self.requestEventType = RequestEventType.GROUP_INVITE
                    case _:
                        self.requestEventType = RequestEventType.UNKNOW
            case _:
                self.requestEventType = RequestEventType.UNKNOW
