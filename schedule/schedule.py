import asyncio
import traceback
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
            case MessageType.PRIVATE_MESSAGE:
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
            try:
                if i.judge(messageInfo):
                    print(f"触发应用{i.applicationInfo.name}")
                    from functools import partial

                    match i.applicationCostType:
                        case ApplicationCostType.NORMAL:
                            asyncio.create_task(i.process(messageInfo))
                            # await i.process(messageInfo)
                        case ApplicationCostType.HIGH_TIME_HIGH_PERFORMANCE:
                            consuming_time_process_queue.put(
                                lambda: i.process(messageInfo)
                            )
                        case ApplicationCostType.HIGH_TIME_LOW_PERFORMANCE:
                            asyncio.create_task(i.process(messageInfo))
                    if not i.canContinue:
                        return
            except Exception as e:
                print(
                    f"应用{i.applicationInfo.name}出错: {e},line:{traceback.extract_tb(e.__traceback__)[0][1]}"
                )
