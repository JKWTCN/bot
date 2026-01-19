import logging
import time
from datetime import datetime

from data.application.meta_application import MetaMessageApplication
from data.enumerates import ApplicationCostType, MetaEventType
from data.message.meta_message_info import MetaMessageInfo
from data.application.application_info import ApplicationInfo
from application.bank_application import calculate_all_interest, should_calculate_interest, update_last_interest_calculation_time


class BankInterestApplication(MetaMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("银行利息自动更新", "每天自动计算银行利息")
        super().__init__(applicationInfo, 5, True, ApplicationCostType.NORMAL)
        self.last_interest_date = None

    async def process(self, message: MetaMessageInfo):
        """处理meta事件，在机器人启动时检查是否需要计算利息"""
        # 只在机器人启动时处理
        if message.metaEventType == MetaEventType.HEART_BEAT:
            await self.check_and_calculate_interest()

    async def check_and_calculate_interest(self):
        """检查是否需要计算利息，如果需要则计算所有用户的利息"""
        # 检查是否需要计算利息
        if await should_calculate_interest():
            logging.info("开始检查是否需要计算银行利息...")

            # 计算所有用户的利息
            interest_count = await calculate_all_interest()

            if interest_count > 0:
                logging.info(f"已为{interest_count}位用户自动计算了银行利息")

            # 更新最后计算利息的时间
            await update_last_interest_calculation_time()
            self.last_interest_date = datetime.now().date()
        else:
            # logging.info("今天已经计算过银行利息，跳过")
            pass