import sqlite3
import time
import re
import logging

from data.application.group_message_application import GroupMessageApplication
from data.enumerates import ApplicationCostType
from function.datebase_other import change_point, find_point
from function.datebase_user import get_user_name
from data.message.group_message_info import GroupMessageInfo
from function.say import ReplySay
from tools.tools import load_setting, HasAllKeyWords, FindNum, is_today, GetNowDay
from data.application.application_info import ApplicationInfo


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


# 批量计算所有用户的利息
def calculate_all_interest():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    
    # 获取所有用户
    cur.execute("SELECT user_id FROM bank_account")
    users = cur.fetchall()
    
    interest_count = 0
    current_time = int(time.time())
    
    for user in users:
        user_id = user[0]
        
        # 获取账户信息
        cur.execute("SELECT balance, last_interest_time FROM bank_account WHERE user_id=?", (user_id,))
        data = cur.fetchall()
        
        if len(data) > 0:
            balance, last_interest_time = data[0]
            
            # 检查是否已经过了一天
            if current_time - last_interest_time >= 86400 and balance > 0:
                # 计算利息
                interest = int(balance * 0.01)  # 1%的利息
                
                if interest > 0:
                    # 更新余额和最后计息时间
                    new_balance = balance + interest
                    cur.execute("UPDATE bank_account SET balance=?, last_interest_time=? WHERE user_id=?", 
                               (new_balance, current_time, user_id))
                    interest_count += 1
    
    conn.commit()
    conn.close()
    
    if interest_count > 0:
        logging.info(f"已为{interest_count}位用户计算了利息")
    
    return interest_count


# 获取最后计算利息的时间
def get_last_interest_calculation_time():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT last_calculation_time FROM bank_interest_record ORDER BY id DESC LIMIT 1")
    data = cur.fetchone()
    conn.close()
    
    if data:
        return data[0]
    else:
        return 0


# 更新最后计算利息的时间
def update_last_interest_calculation_time():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    current_time = int(time.time())
    cur.execute("UPDATE bank_interest_record SET last_calculation_time=? WHERE id=1", (current_time,))
    conn.commit()
    conn.close()
    return current_time


# 检查是否需要计算利息
def should_calculate_interest():
    last_calculation_time = get_last_interest_calculation_time()
    current_time = int(time.time())
    
    # 如果从未计算过利息，则需要计算
    if last_calculation_time == 0:
        return True
    
    # 检查是否在同一天
    from tools.tools import is_today
    return not is_today(current_time, last_calculation_time)


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
                    f"你的积分不足喵！当前积分：{current_points}"
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
                    f"银行余额不足喵！当前银行余额：{bank_balance}"
                )
                return
            
            # 从银行取出
            update_bank_balance(message.senderId, -amount, "withdraw")
            
            # 添加到用户积分
            current_points = find_point(message.senderId)
            change_point(message.senderId, message.groupId, current_points + amount)
            
            # 获取新的银行余额
            new_bank_balance = get_bank_balance(message.senderId)
            
            await ReplySay (
                message.websocket,
                message.groupId,
                message.messageId,
                f"成功从银行取出{amount}积分喵！当前银行余额：{new_bank_balance}"
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
                    f"成功领取{interest}积分利息喵！当前银行余额：{bank_balance}"
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