from data.message.meta_message_info import MetaMessageInfo
from data.application.meta_application import MetaMessageApplication
from data.enumerates import MessageType, MetaEventType, ApplicationCostType
from data.application.application_info import ApplicationInfo
from tools.tools import GetNowHour, GetNowMinute, IsToday
from function.say import SayAndAt
from schedule.register import RegisterApplication
from function.group_setting import DumpGroupSetting, LoadGroupSetting
from tools.tools import load_setting, dump_setting, IsToday
from function.group_operation import GroupSign
import time


class GroupSignApplication(MetaMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("群签到", "群签到", False)
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    async def process(self, message: MetaMessageInfo):
        """处理元消息"""
        _setting = load_setting("group_sign", [])
        i = 0
        for groupId, siginTime in _setting:
            if not IsToday(siginTime):
                _setting[i][1] = time.time()
                dump_setting("group_sign", _setting)
                await GroupSign(message.websocket, groupId)

    def judge(self, message: MetaMessageInfo) -> bool:
        """判断是否触发应用"""
        if message.metaEventType == MetaEventType.HEART_BEAT:
            if GetNowHour() >= 0:
                for groupId, siginTime in load_setting("group_sign", []):
                    if not IsToday(siginTime):
                        return True
        return False
