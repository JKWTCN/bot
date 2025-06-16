class MessageInfo:
    time: int
    botId: int
    rawMessage: dict

    def __init__(self, rawMessage: dict):
        self.rawMessage = rawMessage
        self.time = rawMessage["time"]
        self.botId = rawMessage["botId"]
