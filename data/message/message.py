from abc import ABC
from data.enumerates import MessageType
from message_info import MessageInfo


class Message(ABC):

    messageType: MessageType

    messageInfo: MessageInfo

