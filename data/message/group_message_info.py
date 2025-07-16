import traceback
from data.message.message_info import MessageInfo
from data.enumerates import MessageType


class GroupMessageInfo(MessageInfo):
    senderId: int
    groupId: int
    messageId: int

    # plainTextMessage = ""
    # atList = []
    # replyMessageId = -1
    # imageFileList = []
    # fileList = []
    # faceList = []

    def __init__(self, websocket, rawMessage: dict):
        self.plainTextMessage = ""
        self.atList = []
        self.replyMessageId = -1
        self.imageFileList = []
        self.fileList = []
        self.faceList = []
        self.readMessage = ""
        try:
            super().__init__(websocket, rawMessage)
            self.messageType = MessageType.GROUP_MESSAGE
            self.groupId = self.rawMessage["group_id"]
            self.senderId = self.rawMessage["user_id"]
            self.messageId = self.rawMessage["message_id"]
            for i in self.rawMessage["message"]:
                match i["type"]:
                    case "image":
                        self.imageFileList.append(i["data"]["file"])
                        self.readMessage += f"[图片]"
                    case "file":
                        pass
                    case "reply":
                        self.replyMessageId = int(i["data"]["id"])
                        self.readMessage += f"[回复:{i['data']['id']}]"
                    case "at":
                        self.atList.append(int(i["data"]["qq"]))
                        self.readMessage += f"[at:{i['data']['qq']}]"
                    case "text":
                        self.plainTextMessage += i["data"]["text"]
                        self.readMessage += i["data"]["text"]
                    case "face":
                        self.faceList.append(i["data"]["id"])
                        self.readMessage += f"[表情:{i['data']['raw']['faceText']}]"
        except Exception as e:
            print(f"初始化出错: {e},line:{traceback.extract_tb(e.__traceback__)[0][1]}")
