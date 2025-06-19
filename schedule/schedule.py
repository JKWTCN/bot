import asyncio
from data.message.message_info import MessageInfo
import schedule.application_list as application_list
from data.enumerates import MessageType, ApplicationCostType
from schedule.consuming_high_time_queue import consuming_time_process_queue


class Schedule:
    def __init__(self) -> None:
        pass

    async def processMessage(self, messageInfo: MessageInfo):
        applicationList: application_list.ApplicationList
        match messageInfo.messageType:
            case MessageType.GROUP_MESSAGE:
                applicationList = application_list.groupMessageApplicationList
            case MessageType.PRIVATE_MESSSAGE:
                applicationList = application_list.privateMessageApplicationList
            case MessageType.NOTICE:
                applicationList = application_list.noticeApplicationList
            case MessageType.META:
                applicationList = application_list.metaApplicationList
            case MessageType.REQUEST:
                applicationList = application_list.requestApplicationList
            case MessageType.OTHER:
                applicationList = application_list.otherApplicationList
        for i in applicationList.get():
            if i.judge(messageInfo):
                match i.applicationCostType:
                    case ApplicationCostType.NORMAL:
                        await i.process(messageInfo)
                    case ApplicationCostType.HIGH_TIME_HIGH_PERFORMANCE:
                        consuming_time_process_queue.put(await i.process(messageInfo))
                    case ApplicationCostType.HIGH_TIME_LOW_PERFORMANCE:
                        asyncio.create_task(i.process(messageInfo))
                if not i.isNotEnd:
                    return
