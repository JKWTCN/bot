from data.message.message_post_type import MessagePostType, string2MessagePostType
from data.message.message_info import MessageInfo


class PrivateMesssageInfo(MessageInfo):
    messagePostType: MessagePostType
    senderId: int
    messageId: int

    painTextMessage = ""
    replyMessageId = -1
    imageFileList = []

    def __init__(self, rawMessage: dict):
        super().__init__(rawMessage)
        self.messagePostType = string2MessagePostType(self.rawMessage["post_type"])
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
