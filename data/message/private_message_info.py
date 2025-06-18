from data.message.message_info import MessageInfo
from data.enumerates import MessageType


class PrivateMesssageInfo(MessageInfo):
    senderId: int
    messageId: int

    painTextMessage = ""
    replyMessageId = -1
    imageFileList = []

    def __init__(self, websocket, rawMessage: dict):
        super().__init__(websocket, rawMessage)
        self.messageType = MessageType.PRIVATE_MESSSAGE
        self.senderId = self.rawMessage["user_id"]
        self.messageId = self.rawMessage["message_id"]
        for i in self.rawMessage["message"]:
            match i["type"]:
                case "image":
                    file = i["data"]["file"]
                case "file":
                    pass
                case "reply":
                    self.replyMessageId = i["data"]["id"]
                case "text":
                    self.painTextMessage += i["data"]["text"]
