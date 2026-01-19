import asyncio
import logging
import traceback
from data.message.message_info import MessageInfo
import schedule.application_list as application_list
from data.enumerates import MessageType, ApplicationCostType, ApplicationType
from tools.tools import load_setting
from function.datebase_user import get_user_name
from data.message.group_message_info import GroupMessageInfo
from function.database_group import GetGroupName


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
                    if i.applicationType != ApplicationType.META:
                        if not load_setting("debug_mode", False):
                            if isinstance(messageInfo, GroupMessageInfo):
                                print(
                                    f"触发应用: {get_user_name(messageInfo.senderId,messageInfo.groupId)}({messageInfo.senderId}) {GetGroupName(messageInfo.groupId)}({messageInfo.groupId}):{i.applicationInfo.name}: {i.applicationInfo.info}"
                                )
                            else:
                                print(
                                    f"触发应用: {i.applicationInfo.name}: {i.applicationInfo.info}"
                                )
                        else:
                            if isinstance(messageInfo, GroupMessageInfo):
                                logging.info(
                                    f"触发应用: {get_user_name(messageInfo.senderId,messageInfo.groupId)}({messageInfo.senderId}) {GetGroupName(messageInfo.groupId)}({messageInfo.groupId}):{i.applicationInfo.name}: {i.applicationInfo.info}"
                                )
                            else:
                                logging.info(
                                    f"触发应用: {i.applicationInfo.name}: {i.applicationInfo.info}"
                                )
                    match i.applicationCostType:
                        case ApplicationCostType.NORMAL:
                            # 普通任务：立即创建后台任务
                            asyncio.create_task(i.process(messageInfo))
                        case ApplicationCostType.HIGH_TIME_HIGH_PERFORMANCE:
                            # 高耗时高优任务：提交到队列异步处理
                            async def task_wrapper():
                                await i.process(messageInfo)
                            asyncio.create_task(task_wrapper())
                        case ApplicationCostType.HIGH_TIME_LOW_PERFORMANCE:
                            # 高耗时低优任务：创建后台任务
                            asyncio.create_task(i.process(messageInfo))
                    if not i.canContinue:
                        return
            except Exception as e:
                logging.error(
                    f"应用{i.applicationInfo.name}出错:{e},{traceback.format_exc()}"
                )
