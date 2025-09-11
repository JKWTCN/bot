# 统计群友抽奖次数
import logging
import sqlite3
import time


from function.datebase_user import get_user_name
from function.database_group import GetGroupName
from function.ranking import update_value, Ranking


def change_point(user_id: int, group_id: int, point: int):
    if point >= 9223372036854775807:
        logging.info(
            f"{get_user_name(user_id, group_id)}({user_id}),在群{GetGroupName(group_id)}({group_id})爆分了!!!"
        )
        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()
        cur.execute(
            "UPDATE user_point SET point=? WHERE user_id=?",
            (0, user_id),
        )
        conn.commit()
        conn.close()
        return False
    
    # 获取当前积分
    current_point = find_point(user_id)
    
    # 检查积分是否增加
    if point > current_point:
        # 积分增加，检查是否有借款需要扣除
        from application.bank_application import check_and_deduct_loan
        final_point = check_and_deduct_loan(user_id, group_id, point)
        
        # 如果积分被借款扣除，更新point值
        if final_point != point:
            point = final_point
            logging.info(f"用户{user_id}的积分被借款扣除，剩余积分：{point}")
    
    point = round(point, 3)
    try:
        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()
        cur.execute(
            "UPDATE user_point SET point=? WHERE user_id=?",
            (point, user_id),
        )
        conn.commit()
        conn.close()
    except OverflowError:
        logging.info(
            f"{get_user_name(user_id, group_id)}({user_id}),在群{GetGroupName(group_id)}({group_id})爆分了!!!"
        )
        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()
        cur.execute(
            "UPDATE user_point SET point=? WHERE user_id=?",
            (0, user_id),
        )
        conn.commit()
        conn.close()
        return False
    update_value(Ranking(user_id, group_id, point, int(time.time()), 1))
    return True


def find_gambling_times(user_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT times FROM gambling where user_id=?", (user_id,))
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO gambling VALUES(?,?)",
            (
                user_id,
                0,
            ),
        )
        conn.commit()
        conn.close()
        return 0
    else:
        # print(data)
        return data[0][0]


# 判断是否在不欢迎名单
def in_unwelcome(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM unwelcome where user_id=? and group_id=?", (user_id, group_id)
    )
    data = cur.fetchall()
    # print(data[0][1])
    conn.close()
    if len(data) != 0:
        return (True, data[0][1])
    return (False, 0)


# 增加数据库记录的总抽奖次数
def add_gambling_times(user_id: int, add_times: int):
    now_times = find_gambling_times(user_id)
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE gambling SET times=? WHERE user_id=?",
        (
            now_times + add_times,
            user_id,
        ),
    )
    conn.commit()
    conn.close()


# 查找积分
def find_point(user_id) -> int:
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM user_point where user_id=?", (user_id,))
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute("INSERT INTO user_point VALUES(?,?,?)", (user_id, 50, 0))
        conn.commit()
        conn.close()
        return 0
    else:
        # print(data[0][1])
        conn.close()
        return int(round(data[0][1], 3))
        # return cur.fetchall()


# 获取上次获取群成员列表的时间
def get_last_time_get_group_member_list():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT record_time FROM record where record_name=?",
        ("last_time_get_group_member_list",),
    )
    data = cur.fetchall()
    conn.close()
    return data[0][0]


# 更新上次获取群成员列表的时间
def updata_last_time_get_group_member_list():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE record SET record_time=? WHERE record_name=?",
        (time.time(), "last_time_get_group_member_list"),
    )
    conn.commit()
    conn.close()


# 添加不欢迎名单
def add_unwelcome(user_id: int, time: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO unwelcome VALUES(?,?,?)", (user_id, time, group_id))
    conn.commit()
    conn.close()
