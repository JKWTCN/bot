import traceback
from data.message.message_info import MessageInfo
from data.message.message_post_type import MessagePostType, string2MessagePostType


class GroupMesssageInfo(MessageInfo):
    messagePostType: MessagePostType
    senderId: int
    groupId: int
    messageId: int

    painTextMessage = ""
    atList = []
    replyMessageId = -1
    imageFileList = []
    fileList = []

    def __init__(self, websocket, rawMessage: dict):
        try:
            super().__init__(websocket, rawMessage)
            self.messagePostType = string2MessagePostType(self.rawMessage["post_type"])
            self.groupId = self.rawMessage["group_id"]
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
                    case "at":
                        self.atList.append(i["data"]["qq"])
                    case "text":
                        self.painTextMessage += i["data"]["text"]
        except Exception as e:
            print(f"初始化出错: {e},line:{traceback.extract_tb(e.__traceback__)[0][1]}")
