from venv import logger
import tushare as ts
from private import tushare_token
import time
import sqlite3
from Class.Group_member import get_user_name
from tools import load_setting, dump_setting


# B股股指
def GetBShock():
    ts.set_token(tushare_token)
    df = ts.realtime_quote(ts_code="000003.SH")
    return df.PRICE[0]


# 狗狗币
def GetDogeCoin():
    import re
    import requests

    try:
        r = requests.get("https://bitcompare.net/zh-cn/coins/dogecoin")
        # with open("tmp.txt", "w", encoding="utf-8") as f:
        #     f.write(r.text)
        pattern = re.compile(
            'placeholder="0.00" min="0" step="1" value="(.*?)"/>',
        )
        m = pattern.findall(r.text)
        setting = load_setting()
        setting["kohlrabi_price"] = float(m[0])
        dump_setting(setting)
        return m[0]
    except:
        setting = load_setting()
        logger.info(
            "获取大头菜价格失败，使用上一次的价格:{}".format(setting["kohlrabi_price"])
        )
        return setting["kohlrabi_price"]


# 获取大头菜价格
def GetNowPrice():
    now_price = GetDogeCoin()
    return round(float(now_price) * 1000, 3)


# 获取我的本周交易记录
def GetMyKohlrabi(user_id: int, group_id: int):
    now_week = time.strftime("%W")
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT nums FROM kohlrabi_week where user_id=? and group_id=?;",
        (
            user_id,
            group_id,
        ),
    )
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO kohlrabi_week (user_id,group_id,nums,now_weeks)VALUES (?,?,0,?);",
            (
                user_id,
                group_id,
                now_week,
            ),
        )
        conn.commit()
        return 0
    else:
        return data[0][0]


# 定期清理过期对的大头菜
def ClearKohlrabi():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM kohlrabi_week WHERE  now_weeks != ?;", (time.strftime("%W"),)
    )
    conn.commit()


# 改变大头菜本周交易记录
def ChangeMyKohlrabi(user_id: int, group_id: int, nums: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE kohlrabi_week SET nums = ? WHERE user_id = ? AND group_id = ?;",
        (nums, user_id, group_id),
    )
    conn.commit()


# 梭哈
def ShowHand(user_id: int, group_id: int):
    from bot_database import change_point, find_point
    import math

    now_num = GetMyKohlrabi(user_id, group_id)
    now_point = find_point(user_id)
    now_price = GetNowPrice()
    if now_point > now_price:
        num = math.trunc(now_point / now_price)
        (all_buy, all_buy_cost, all_sell, all_sell_price) = GetRecordKohlrabi(
            user_id, group_id
        )
        all_buy = all_buy + num
        get_point = round(now_price * num, 3)
        all_buy_cost = round(all_buy_cost + get_point, 3)
        change_point(user_id, group_id, now_point - get_point)
        ChangeMyKohlrabi(user_id, group_id, now_num + num)
        UpdateRecordKohlrabi(
            user_id, group_id, all_buy, all_buy_cost, all_sell, all_sell_price
        )
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {
                            "text": f"{get_user_name(user_id, group_id)},梭哈成功喵,单价{now_price},您的大头菜数目:{now_num}->{now_num + num},积分:{now_point}->{now_point - get_point}。"
                        },
                    },
                    {
                        "type": "text",
                        "data": {"text": "大头菜会在本周末过期,请及时卖出喵。"},
                    },
                ],
            },
        }
    else:
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {
                            "text": f"{get_user_name(user_id, group_id)},没积分?没积分不要来买大头菜喵!"
                        },
                    },
                ],
            },
        }
    return payload


# 购买大头菜
def BuyKohlrabi(user_id: int, group_id: int, num: int):
    from bot_database import change_point, find_point

    now_num = GetMyKohlrabi(user_id, group_id)
    now_point = find_point(user_id)
    now_price = GetNowPrice()
    if now_point >= now_price * num:
        (all_buy, all_buy_cost, all_sell, all_sell_price) = GetRecordKohlrabi(
            user_id, group_id
        )
        all_buy = all_buy + num
        get_point = round(now_price * num, 3)
        all_buy_cost = round(all_buy_cost + get_point, 3)
        change_point(user_id, group_id, now_point - get_point)
        ChangeMyKohlrabi(user_id, group_id, now_num + num)
        UpdateRecordKohlrabi(
            user_id, group_id, all_buy, all_buy_cost, all_sell, all_sell_price
        )
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {
                            "text": f"{get_user_name(user_id, group_id)},买入成功喵,单价{now_price},您的大头菜数目:{now_num}->{now_num + num},积分:{now_point}->{now_point - get_point}。"
                        },
                    },
                    {
                        "type": "text",
                        "data": {"text": "大头菜会在每周一0点过期,请及时卖出喵。"},
                    },
                ],
            },
        }
    else:
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {
                            "text": f"{get_user_name(user_id, group_id)},没积分?没积分不要来买大头菜喵!"
                        },
                    },
                ],
            },
        }
    return payload


# 获取大头菜相关统计信息
def GetRecordKohlrabi(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT all_buy,all_buy_cost,all_sell,all_sell_price FROM kohlrabi_record where user_id=? and group_id=?;",
        (
            user_id,
            group_id,
        ),
    )
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO kohlrabi_record (user_id,group_id,all_buy,all_buy_cost,all_sell,all_sell_price)VALUES(?, ?, ?, ?, ?, ?);",
            (user_id, group_id, 0, 0, 0, 0),
        )
        conn.commit()
        return (0, 0, 0, 0)
    else:
        return (data[0][0], data[0][1], data[0][2], data[0][3])


# 更新大头菜相关统计信息
def UpdateRecordKohlrabi(
    user_id: int, group_id: int, all_buy, all_buy_cost, all_sell, all_sell_price
):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE kohlrabi_record SET all_buy=?,all_buy_cost=?,all_sell=?,all_sell_price=? WHERE user_id = ? AND group_id = ?;",
        (all_buy, all_buy_cost, all_sell, all_sell_price, user_id, group_id),
    )
    conn.commit()


# 售出大头菜
def SellKohlrabi(user_id: int, group_id: int, num: int):
    now_num = GetMyKohlrabi(user_id, group_id)
    if now_num > 0 and num <= now_num:
        from bot_database import change_point, find_point

        now_point = find_point(user_id)
        now_price = GetNowPrice()
        (all_buy, all_buy_cost, all_sell, all_sell_price) = GetRecordKohlrabi(
            user_id, group_id
        )
        get_point = round(now_price * num, 3)
        change_point(user_id, group_id, now_point + get_point)
        ChangeMyKohlrabi(user_id, group_id, now_num - num)
        all_sell = all_sell + num
        all_sell_price = round(all_sell_price + get_point, 3)
        UpdateRecordKohlrabi(
            user_id, group_id, all_buy, all_buy_cost, all_sell, all_sell_price
        )
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {
                            "text": f"{get_user_name(user_id, group_id)},售出成功喵,单价{now_price},你的大头菜库存:{now_num}->{now_num - num},积分:{now_point}->{now_point + get_point}喵!"
                        },
                    },
                ],
            },
        }
    else:
        payload = {
            "action": "send_msg",
            "params": {
                "group_id": group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {
                            "text": f"{get_user_name(user_id, group_id)},大头菜数目不够喵,你当前的大头菜数目为:{now_num}个喵!"
                        },
                    },
                ],
            },
        }
    return payload
