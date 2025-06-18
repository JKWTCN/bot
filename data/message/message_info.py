from data.enumerates import MessageType


class MessageInfo:
    time: int
    botId: int
    rawMessage: dict
    messageType: MessageType

    def __init__(self, websocket, rawMessage: dict):
        self.rawMessage = rawMessage
        self.time = rawMessage["time"]
        self.botId = rawMessage["self_id"]
        self.websocket = websocket
