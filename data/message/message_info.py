from data.enumerates import MessageType


class MessageInfo:

    def __init__(self, websocket, rawMessage: dict):
        self.rawMessage = rawMessage
        self.time = rawMessage["time"]
        self.botId = rawMessage["self_id"]
        self.websocket = websocket
        self.messageType: MessageType
