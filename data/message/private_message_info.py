from data.message.message_info import MessageInfo
from data.enumerates import MessageType


class PrivateMesssageInfo(MessageInfo):

    def __init__(self, websocket, rawMessage: dict):
        self.senderId: int
        self.messageId: int

        self.plainTextMessage = ""
        self.replyMessageId = -1
        self.imageFileList = []
        self.faceList = []
        super().__init__(websocket, rawMessage)
        self.messageType = MessageType.PRIVATE_MESSAGE
        self.senderId = self.rawMessage["user_id"]
        self.messageId = self.rawMessage["message_id"]
        for i in self.rawMessage["message"]:
            match i["type"]:
                case "image":
                    self.imageFileList.append(i["data"]["file"])
                case "file":
                    pass
                case "reply":
                    self.replyMessageId = i["data"]["id"]
                case "text":
                    self.plainTextMessage += i["data"]["text"]
                case "face":
                    self.faceList.append(i["data"]["id"])
