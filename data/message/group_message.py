from message_post_type import MessagePostType, string2MessagePostType
from message_info import MessageInfo


class GroupMesssageInfo(MessageInfo):
    messagePostType: MessagePostType
    senderId: int
    groupId: int
    messageId: int

    painTextMessage = ""
    atList = []
    replyMessageId = -1
    imageFileList = []

    def __init__(self, rawMessage: dict):
        super().__init__(rawMessage)
        self.messagePostType = string2MessagePostType(self.rawMessage["post_type"])
        self.groupId = self.rawMessage["group_id"]
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
                case "at":
                    self.atList.append(i["data"]["qq"])
                case "text":
                    self.painTextMessage += i["data"]["text"]
