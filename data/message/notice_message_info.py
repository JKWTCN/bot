from data.enumerates import MessageType, NoticeType
from data.message.message_info import MessageInfo


class NoticeMessageInfo(MessageInfo):
    senderId: int
    messageId: int
    noticeEventType: NoticeType

    def __init__(self, websocket, rawMessage: dict):
        super().__init__(websocket, rawMessage)
        self.messageType = MessageType.NOTICE
        match rawMessage["notice_type"]:
            case "group_upload":
                self.noticeEventType = NoticeType.GROUP_FILE_UPLOAD
            case "group_admin":
                self.noticeEventType = NoticeType.GROUP_ADMIN_CHANGE
            case "group_decrease":
                self.noticeEventType = NoticeType.GROUP_MEMBER_DELETE
            case "group_increase":
                self.noticeEventType = NoticeType.GROUP_MEMBER_ADD
            case "group_ban":
                self.noticeEventType = NoticeType.GROUP_BAN_CHAT
            case "friend_add":
                self.noticeEventType = NoticeType.FRIEND_ADD
            case "group_recall":
                self.noticeEventType = NoticeType.GROUP_MESSAGE_RECALL
            case "friend_recall":
                self.noticeEventType = NoticeType.FRIEND_MESSAGE_RECALL
            case "notify":
                match rawMessage["sub_type"]:
                    case "poke":
                        self.noticeEventType = NoticeType.GROUP_POKE
                    case "lucky_king":
                        self.noticeEventType = NoticeType.GROUP_LUCK_DOG
                    case "honor":
                        self.noticeEventType = NoticeType.GROUP_HONOR_CHANGE
                    case _:
                        self.noticeEventType = NoticeType.UNKNOW
            case _:
                self.noticeEventType = NoticeType.UNKNOW
