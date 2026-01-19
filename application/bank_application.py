import time
import re
import logging
import asyncio
import sqlite3

from data.application.group_message_application import GroupMessageApplication
from data.enumerates import ApplicationCostType
from function.datebase_other import change_point, find_point
from function.datebase_user import get_user_name
from data.message.group_message_info import GroupMessageInfo
from function.say import ReplySay
from tools.tools import load_setting, HasAllKeyWords, FindNum, is_today, GetNowDay
from data.application.application_info import ApplicationInfo

# 使用异步数据库连接池
from database.db_pool import bot_db_pool


# 创建银行账户表
def create_bank_table():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bank_account (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0,
        last_interest_time INTEGER DEFAULT 0,
        total_deposit INTEGER DEFAULT 0,
        total_withdraw INTEGER DEFAULT 0
    )
    """)
    
    # 创建银行利息计算记录表
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bank_interest_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        last_calculation_time INTEGER DEFAULT 0
    )
    """)
    
    # 创建每日取出积分记录表
    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_withdraw_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        UNIQUE(user_id, date)
    )
    """)
    
    # 检查是否有记录，如果没有则插入一条
    cur.execute("SELECT COUNT(*) FROM bank_interest_record")
    count = cur.fetchone()[0]
    if count == 0:
        cur.execute("INSERT INTO bank_interest_record (last_calculation_time) VALUES (0)")
    
    conn.commit()
    conn.close()


# 获取银行账户余额
def get_bank_balance(user_id: int) -> int:
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT balance FROM bank_account WHERE user_id=?", (user_id,))
    data = cur.fetchall()
    conn.close()
    
    if len(data) == 0:
        # 如果没有账户，创建一个
        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()
        cur.execute("INSERT INTO bank_account (user_id, balance, last_interest_time) VALUES (?, ?, ?)",
                   (user_id, 0, int(time.time())))
        conn.commit()
        conn.close()
        return 0
    else:
        return data[0][0]


# 更新银行账户余额
def update_bank_balance(user_id: int, amount: int, operation_type: str):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    
    # 获取当前余额
    cur.execute("SELECT balance, total_deposit, total_withdraw FROM bank_account WHERE user_id=?", (user_id,))
    data = cur.fetchall()
    
    if len(data) == 0:
        # 如果没有账户，创建一个
        cur.execute("INSERT INTO bank_account (user_id, balance, last_interest_time) VALUES (?, ?, ?)",
                   (user_id, amount, int(time.time())))
        if operation_type == "deposit":
            cur.execute("UPDATE bank_account SET total_deposit=? WHERE user_id=?", (amount, user_id))
    else:
        balance, total_deposit, total_withdraw = data[0]
        new_balance = balance + amount
        
        # 更新余额
        cur.execute("UPDATE bank_account SET balance=? WHERE user_id=?", (new_balance, user_id))
        
        # 更新总存款或总取款
        if operation_type == "deposit" and amount > 0:
            cur.execute("UPDATE bank_account SET total_deposit=? WHERE user_id=?", 
                       (total_deposit + amount, user_id))
        elif operation_type == "withdraw" and amount < 0:
            cur.execute("UPDATE bank_account SET total_withdraw=? WHERE user_id=?", 
                       (total_withdraw + abs(amount), user_id))
    
    conn.commit()
    conn.close()
    return True


# 计算并发放利息
def calculate_interest(user_id: int, interest_rate: float = 0.01) -> int:
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    
    # 获取账户信息
    cur.execute("SELECT balance, last_interest_time FROM bank_account WHERE user_id=?", (user_id,))
    data = cur.fetchall()
    
    if len(data) == 0:
        conn.close()
        return 0
    
    balance, last_interest_time = data[0]
    current_time = int(time.time())
    
    # 检查是否已经过了一天（86400秒）
    if current_time - last_interest_time >= 86400:
        # 计算利息
        interest = int(balance * interest_rate)
        
        if interest > 0:
            # 更新余额和最后计息时间
            new_balance = balance + interest
            cur.execute("UPDATE bank_account SET balance=?, last_interest_time=? WHERE user_id=?", 
                       (new_balance, current_time, user_id))
            conn.commit()
            
            logging.info(f"用户{user_id}获得利息{interest}，当前余额{new_balance}")
            conn.close()
            return interest
    
    conn.close()
    return 0


# 批量计算所有用户的利息 (异步版本)
async def calculate_all_interest():
    async with bot_db_pool.acquire() as conn:
        cur = await conn.execute("SELECT user_id FROM bank_account")
        users = await cur.fetchall()

    interest_count = 0
    current_time = int(time.time())

    for user in users:
        user_id = user[0]

        # 获取账户信息
        result = await bot_db_pool.fetchone(
            "SELECT balance, last_interest_time FROM bank_account WHERE user_id=?",
            (user_id,)
        )

        if result:
            balance, last_interest_time = result

            # 检查是否已经过了一天
            if current_time - last_interest_time >= 86400 and balance > 0:
                # 计算利息
                interest = int(balance * 0.01)  # 1%的利息

                if interest > 0:
                    # 更新余额和最后计息时间
                    new_balance = balance + interest
                    await bot_db_pool.execute(
                        "UPDATE bank_account SET balance=?, last_interest_time=? WHERE user_id=?",
                        (new_balance, current_time, user_id)
                    )
                    interest_count += 1

    if interest_count > 0:
        logging.info(f"已为{interest_count}位用户计算了利息")

    return interest_count


# 获取最后计算利息的时间 (异步版本)
async def get_last_interest_calculation_time():
    result = await bot_db_pool.fetchone(
        "SELECT last_calculation_time FROM bank_interest_record ORDER BY id DESC LIMIT 1"
    )
    if result:
        return result[0]
    return 0


# 更新最后计算利息的时间 (异步版本)
async def update_last_interest_calculation_time():
    current_time = int(time.time())
    await bot_db_pool.execute(
        "UPDATE bank_interest_record SET last_calculation_time=? WHERE id=1",
        (current_time,)
    )
    return current_time


# 获取用户今日已取出的积分总额
def get_daily_withdraw_amount(user_id: int) -> int:
    """获取用户今日已取出的积分总额"""
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    
    # 获取今日日期（时间戳）
    today = GetNowDay()
    
    # 查询用户今日取出的积分总额
    cur.execute("SELECT amount FROM daily_withdraw_record WHERE user_id=? AND date=?", (user_id, today))
    data = cur.fetchone()
    
    conn.close()
    
    if data:
        return data[0]
    else:
        return 0


# 更新用户每日取出积分记录
def update_daily_withdraw_record(user_id: int, amount: int):
    """更新用户每日取出积分记录"""
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    
    # 获取今日日期（时间戳）
    today = GetNowDay()
    
    # 检查是否已有今日记录
    cur.execute("SELECT amount FROM daily_withdraw_record WHERE user_id=? AND date=?", (user_id, today))
    data = cur.fetchone()
    
    if data:
        # 更新现有记录
        new_amount = data[0] + amount
        cur.execute("UPDATE daily_withdraw_record SET amount=? WHERE user_id=? AND date=?",
                   (new_amount, user_id, today))
    else:
        # 插入新记录
        cur.execute("INSERT INTO daily_withdraw_record (user_id, date, amount) VALUES (?, ?, ?)",
                   (user_id, today, amount))
    
    conn.commit()
    conn.close()


# 检查是否需要计算利息 (异步版本)
async def should_calculate_interest():
    last_calculation_time = await get_last_interest_calculation_time()
    current_time = int(time.time())

    # 如果从未计算过利息，则需要计算
    if last_calculation_time == 0:
        return True

    # 检查是否在同一天
    from tools.tools import is_today
    return not is_today(current_time, last_calculation_time)


# 检查并扣除借款
def check_and_deduct_loan(user_id: int, group_id: int, point: int) -> int:
    """
    检查用户是否有借款，如果有则从积分中扣除
    
    Args:
        user_id: 用户ID
        group_id: 群组ID
        point: 当前积分
        
    Returns:
        扣除借款后的积分
    """
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    
    try:
        # 查询用户是否有借款
        cur.execute("SELECT amount FROM loan WHERE user_id=? AND group_id=?", (user_id, group_id))
        loan_data = cur.fetchall()
        
        if len(loan_data) > 0:
            loan_amount = loan_data[0][0]
            
            if loan_amount > 0:
                # 计算扣除借款后的积分
                if point >= loan_amount:
                    # 积分足够还清借款
                    final_point = point - loan_amount
                    # 清除借款记录
                    cur.execute("DELETE FROM loan WHERE user_id=? AND group_id=?", (user_id, group_id))
                    conn.commit()
                    logging.info(f"用户{user_id}在群{group_id}还清了{loan_amount}积分的借款")
                else:
                    # 积分不足以还清借款，部分扣除
                    final_point = 0
                    # 更新借款金额
                    remaining_loan = loan_amount - point
                    cur.execute("UPDATE loan SET amount=? WHERE user_id=? AND group_id=?",
                               (remaining_loan, user_id, group_id))
                    conn.commit()
                    logging.info(f"用户{user_id}在群{group_id}部分还款{point}积分，剩余借款{remaining_loan}积分")
                
                return final_point
        
        # 没有借款，返回原积分
        return point
        
    except Exception as e:
        logging.error(f"检查并扣除借款时发生错误: {e}")
        return point
    finally:
        conn.close()


class BankApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("积分银行", "存入积分获取每日利息")
        super().__init__(applicationInfo, 10, False, ApplicationCostType.NORMAL)
        # 确保银行表存在
        create_bank_table()

    async def process(self, message: GroupMessageInfo) -> None:
        # 处理存入积分
        if HasAllKeyWords(message.plainTextMessage, ["乐可", "存入"]):
            # 提取存入金额
            amount = FindNum(message.plainTextMessage)
            if amount <= 0:
                await ReplySay(
                    message.websocket,
                    message.groupId,
                    message.messageId,
                    f"存入金额必须大于0喵！"
                )
                return
            
            # 检查用户是否有足够的积分
            current_points = find_point(message.senderId)
            if current_points < amount:
                await ReplySay(
                    message.websocket,
                    message.groupId,
                    message.messageId,
                    f"你的积分不足喵！当前积分：{current_points} 喵."
                )
                return
            
            # 从用户积分中扣除
            change_point(message.senderId, message.groupId, current_points - amount)
            
            # 存入银行
            update_bank_balance(message.senderId, amount, "deposit")
            
            # 获取银行余额
            bank_balance = get_bank_balance(message.senderId)

            await ReplySay(
                message.websocket,
                message.groupId,
                message.messageId,
                f"成功存入{amount}积分到银行喵！当前银行余额：{bank_balance}"
            )
        
        # 处理取出积分
        elif HasAllKeyWords(message.plainTextMessage, ["乐可", "取出"]):
            # 提取取出金额
            amount = FindNum(message.plainTextMessage)
            if amount <= 0:
                await ReplySay(
                    message.websocket,
                    message.groupId,
                    message.messageId,
                    f"取出金额必须大于0喵！"
                )
                return
            
            # 检查银行余额是否足够
            bank_balance = get_bank_balance(message.senderId)
            if bank_balance < amount:
                await ReplySay(
                    message.websocket,
                    message.groupId,
                    message.messageId,
                    f"银行余额不足喵！当前银行余额：{bank_balance} 喵."
                )
                return
            
            # 检查每日取出限制
            daily_limit = load_setting("daily_point_limit",2000)
            
            if daily_limit != -1:  # -1表示不限制
                # 获取用户今日已取出的积分总额
                daily_withdrawn = get_daily_withdraw_amount(message.senderId)
                
                # 检查是否超出每日限制
                if daily_withdrawn + amount > daily_limit:
                    await ReplySay(
                        message.websocket,
                        message.groupId,
                        message.messageId,
                        f"超出每日取出限制喵！今日已取出{daily_withdrawn}积分，每日最多可取出{daily_limit}积分喵."
                    )
                    return
            
            # 从银行取出
            update_bank_balance(message.senderId, -amount, "withdraw")
            
            # 添加到用户积分
            current_points = find_point(message.senderId)
            change_point(message.senderId, message.groupId, current_points + amount)
            
            # 更新每日取出记录
            if daily_limit != -1:  # 只在有限制时更新记录
                update_daily_withdraw_record(message.senderId, amount)
            
            # 获取新的银行余额
            new_bank_balance = get_bank_balance(message.senderId)
            
            await ReplySay (
                message.websocket,
                message.groupId,
                message.messageId,
                f"成功从银行取出{amount}积分喵！当前银行余额：{new_bank_balance} 喵."
            )
        
        # 处理查询银行余额
        elif HasAllKeyWords(message.plainTextMessage, ["乐可", "银行", "余额"]):
            bank_balance = get_bank_balance(message.senderId)
            await ReplySay (
                message.websocket,
                message.groupId,
                message.messageId,
                f"你的银行余额为：{bank_balance}积分喵"
            )
        
        # 处理领取利息
        elif HasAllKeyWords(message.plainTextMessage, ["乐可", "领取", "利息"]):
            interest = calculate_interest(message.senderId)
            if interest > 0:
                # 获取银行余额
                bank_balance = get_bank_balance(message.senderId)
                await ReplySay(
                    message.websocket,
                    message.groupId,
                    message.messageId,
                    f"成功领取{interest}积分利息喵！当前银行余额：{bank_balance} 喵."
                )
            else:
                await ReplySay(
                    message.websocket,
                    message.groupId,
                    message.messageId,
                    f"暂时没有利息可以领取喵，请确保银行有存款且已过一天喵！"
                )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        return (
            HasAllKeyWords(message.plainTextMessage, ["乐可", "存入"]) or
            HasAllKeyWords(message.plainTextMessage, ["乐可", "取出"]) or
            HasAllKeyWords(message.plainTextMessage, ["乐可", "银行", "余额"]) or
            HasAllKeyWords(message.plainTextMessage, ["乐可", "领取", "利息"])
        )