from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMesssageInfo
from function.say import SayRaw
import random


import base64
import json
import sqlite3
from typing import Dict, List, Optional
from matplotlib import pyplot as plt
import pandas as pd
from plottable import Table


def create_table(db_path: str = "bot.db") -> None:
    """
    创建股票交易记录表
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS stock_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        group_id INTEGER NOT NULL,
        stock_id TEXT NOT NULL,
        buy_avg_price REAL DEFAULT 0,
        buy_total_quantity INTEGER DEFAULT 0,
        buy_total_cost REAL DEFAULT 0,
        sell_avg_price REAL DEFAULT 0,
        sell_total_quantity INTEGER DEFAULT 0,
        sell_total_amount REAL DEFAULT 0,
        current_quantity INTEGER DEFAULT 0,
        current_avg_price REAL DEFAULT 0,
        UNIQUE(user_id, group_id, stock_id)  -- 确保每个用户在同一个群组中对同一只股票只有一条记录
    )
    """
    )

    conn.commit()
    conn.close()


class StockTradingDB:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        create_table(db_path)

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def add_or_update_record(
        self,
        user_id: int,
        group_id: int,
        stock_id: str,
        buy_avg_price: Optional[float] = None,
        buy_total_quantity: Optional[int] = None,
        buy_total_cost: Optional[float] = None,
        sell_avg_price: Optional[float] = None,
        sell_total_quantity: Optional[int] = None,
        sell_total_amount: Optional[float] = None,
        current_quantity: Optional[int] = None,
        current_avg_price: Optional[float] = None,
    ) -> bool:
        """
        添加或更新股票交易记录
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 检查记录是否已存在
        cursor.execute(
            "SELECT * FROM stock_transactions WHERE user_id=? AND group_id=? AND stock_id=?",
            (user_id, group_id, stock_id),
        )
        existing_record = cursor.fetchone()

        try:
            if existing_record:
                # 更新现有记录
                update_fields = []
                update_values = []

                if buy_avg_price is not None:
                    update_fields.append("buy_avg_price=?")
                    update_values.append(buy_avg_price)
                if buy_total_quantity is not None:
                    update_fields.append("buy_total_quantity=?")
                    update_values.append(buy_total_quantity)
                if buy_total_cost is not None:
                    update_fields.append("buy_total_cost=?")
                    update_values.append(buy_total_cost)
                if sell_avg_price is not None:
                    update_fields.append("sell_avg_price=?")
                    update_values.append(sell_avg_price)
                if sell_total_quantity is not None:
                    update_fields.append("sell_total_quantity=?")
                    update_values.append(sell_total_quantity)
                if sell_total_amount is not None:
                    update_fields.append("sell_total_amount=?")
                    update_values.append(sell_total_amount)
                if current_quantity is not None:
                    update_fields.append("current_quantity=?")
                    update_values.append(current_quantity)
                if current_avg_price is not None:
                    update_fields.append("current_avg_price=?")
                    update_values.append(current_avg_price)

                if update_fields:
                    update_query = f"""
                    UPDATE stock_transactions 
                    SET {', '.join(update_fields)} 
                    WHERE user_id=? AND group_id=? AND stock_id=?
                    """
                    update_values.extend([user_id, group_id, stock_id])
                    cursor.execute(update_query, update_values)
            else:
                # 插入新记录
                cursor.execute(
                    """
                    INSERT INTO stock_transactions (
                        user_id, group_id, stock_id, 
                        buy_avg_price, buy_total_quantity, buy_total_cost,
                        sell_avg_price, sell_total_quantity, sell_total_amount,
                        current_quantity, current_avg_price
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        group_id,
                        stock_id,
                        buy_avg_price or 0,
                        buy_total_quantity or 0,
                        buy_total_cost or 0,
                        sell_avg_price or 0,
                        sell_total_quantity or 0,
                        sell_total_amount or 0,
                        current_quantity or 0,
                        current_avg_price or 0,
                    ),
                )

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error adding/updating record: {e}")
            return False
        finally:
            conn.close()

    def delete_record(self, user_id: int, group_id: int, stock_id: str) -> bool:
        """
        删除股票交易记录
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "DELETE FROM stock_transactions WHERE user_id=? AND group_id=? AND stock_id=?",
                (user_id, group_id, stock_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f"Error deleting record: {e}")
            return False
        finally:
            conn.close()

    def get_record(self, user_id: int, group_id: int, stock_id: str) -> Optional[Dict]:
        """
        获取特定股票交易记录
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT 
                    user_id, group_id, stock_id, 
                    buy_avg_price, buy_total_quantity, buy_total_cost,
                    sell_avg_price, sell_total_quantity, sell_total_amount,
                    current_quantity, current_avg_price
                FROM stock_transactions 
                WHERE user_id=? AND group_id=? AND stock_id=?
                """,
                (user_id, group_id, stock_id),
            )

            row = cursor.fetchone()
            if row:
                columns = [
                    "user_id",
                    "group_id",
                    "stock_id",
                    "buy_avg_price",
                    "buy_total_quantity",
                    "buy_total_cost",
                    "sell_avg_price",
                    "sell_total_quantity",
                    "sell_total_amount",
                    "current_quantity",
                    "current_avg_price",
                ]
                return dict(zip(columns, row))
            return None
        except Exception as e:
            print(f"Error getting record: {e}")
            return None
        finally:
            conn.close()

    def get_user_records(self, user_id: int, group_id: int) -> List[Dict]:
        """
        获取用户的所有股票交易记录
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            if group_id:
                cursor.execute(
                    """
                    SELECT 
                        user_id, group_id, stock_id, 
                        buy_avg_price, buy_total_quantity, buy_total_cost,
                        sell_avg_price, sell_total_quantity, sell_total_amount,
                        current_quantity, current_avg_price
                    FROM stock_transactions 
                    WHERE user_id=? AND group_id=?
                    """,
                    (user_id, group_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT 
                        user_id, group_id, stock_id, 
                        buy_avg_price, buy_total_quantity, buy_total_cost,
                        sell_avg_price, sell_total_quantity, sell_total_amount,
                        current_quantity, current_avg_price
                    FROM stock_transactions 
                    WHERE user_id=?
                    """,
                    (user_id,),
                )

            columns = [
                "user_id",
                "group_id",
                "stock_id",
                "buy_avg_price",
                "buy_total_quantity",
                "buy_total_cost",
                "sell_avg_price",
                "sell_total_quantity",
                "sell_total_amount",
                "current_quantity",
                "current_avg_price",
            ]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting user records: {e}")
            return []
        finally:
            conn.close()

    def record_buy_transaction(
        self,
        user_id: int,
        group_id: int,
        stock_id: str,
        buy_price: float,
        buy_quantity: int,
    ) -> bool:
        """
        记录买入交易，自动更新相关字段
        """
        buy_cost = buy_price * buy_quantity
        record = self.get_record(user_id, group_id, stock_id)

        if record:
            # 计算新的买入均价和总数
            total_quantity = record["buy_total_quantity"] + buy_quantity
            total_cost = record["buy_total_cost"] + buy_cost
            new_avg_price = total_cost / total_quantity if total_quantity > 0 else 0

            # 更新当前持仓
            current_quantity = record["current_quantity"] + buy_quantity
            current_avg_price = (
                (record["current_avg_price"] * record["current_quantity"] + buy_cost)
                / current_quantity
                if current_quantity > 0
                else 0
            )

            return self.add_or_update_record(
                user_id=user_id,
                group_id=group_id,
                stock_id=stock_id,
                buy_avg_price=new_avg_price,
                buy_total_quantity=total_quantity,
                buy_total_cost=total_cost,
                current_quantity=current_quantity,
                current_avg_price=current_avg_price,
            )
        else:
            return self.add_or_update_record(
                user_id=user_id,
                group_id=group_id,
                stock_id=stock_id,
                buy_avg_price=buy_price,
                buy_total_quantity=buy_quantity,
                buy_total_cost=buy_cost,
                current_quantity=buy_quantity,
                current_avg_price=buy_price,
            )

    def record_sell_transaction(
        self,
        user_id: int,
        group_id: int,
        stock_id: str,
        sell_price: float,
        sell_quantity: int,
    ) -> bool:
        """
        记录卖出交易，自动更新相关字段
        """
        sell_amount = sell_price * sell_quantity
        record = self.get_record(user_id, group_id, stock_id)

        if not record:
            return False

        if record["current_quantity"] < sell_quantity:
            return False  # 不能卖出超过当前持仓的数量

        # 计算新的卖出均价和总数
        total_sell_quantity = record["sell_total_quantity"] + sell_quantity
        total_sell_amount = record["sell_total_amount"] + sell_amount
        new_sell_avg_price = (
            total_sell_amount / total_sell_quantity if total_sell_quantity > 0 else 0
        )

        # 更新当前持仓
        current_quantity = record["current_quantity"] - sell_quantity
        # 卖出不影响当前均价
        current_avg_price = record["current_avg_price"] if current_quantity > 0 else 0

        return self.add_or_update_record(
            user_id=user_id,
            group_id=group_id,
            stock_id=stock_id,
            sell_avg_price=new_sell_avg_price,
            sell_total_quantity=total_sell_quantity,
            sell_total_amount=total_sell_amount,
            current_quantity=current_quantity,
            current_avg_price=current_avg_price,
        )


from function.datebase_other import find_point, change_point
from enum import Enum


class BuyError(Enum):
    NOT_ENOUGH_POINT = "积分不足"
    STOCK_NOT_FOUND = "股票未找到"
    BUY_SUCCESS = "购买成功"
    BUY_FAIL = "购买失败"


class SellError(Enum):
    NOT_ENOUGH_STOCK = "数目不足"
    STOCK_NOT_FOUND = "股票未找到"
    SELL_SUCCESS = "卖出成功"
    SELL_FAIL = "卖出失败"


def buyStock(user_id: int, group_id: int, stock_id: str, num: int) -> BuyError:
    """
    买入股票
    """
    import tushare as ts
    from private import tushare_token

    ts.set_token(tushare_token)
    try:
        df = ts.realtime_quote(ts_code=stock_id)
    except Exception as e:
        print(f"Error fetching stock data: {e}")
        return BuyError.STOCK_NOT_FOUND
    price = df.PRICE[0]  # type: ignore
    now_point = find_point(user_id)
    change_point(user_id, group_id, now_point - price * num)
    if now_point < price * num:
        return BuyError.NOT_ENOUGH_POINT
    stockDb = StockTradingDB()

    if stockDb.record_buy_transaction(user_id, group_id, stock_id, price, num):
        return BuyError.BUY_SUCCESS
    return BuyError.BUY_FAIL


def sellStock(user_id: int, group_id: int, stock_id: str, num: int) -> SellError:
    """
    卖出股票
    """
    import tushare as ts
    from private import tushare_token

    stockDb = StockTradingDB()
    res = stockDb.get_record(user_id, group_id, stock_id)
    if res is None:
        return SellError.NOT_ENOUGH_STOCK
    elif res["current_quantity"] < num:
        return SellError.NOT_ENOUGH_STOCK
    ts.set_token(tushare_token)
    try:
        df = ts.realtime_quote(ts_code=stock_id)
    except Exception as e:
        print(f"Error fetching stock data: {e}")
        return SellError.STOCK_NOT_FOUND
    price = df.PRICE[0]  # type: ignore
    now_point = find_point(user_id)
    change_point(user_id, group_id, now_point + price * num)
    stockDb.record_sell_transaction(user_id, group_id, stock_id, price, num)
    return SellError.SELL_SUCCESS


def ShowStockMarketByBase64(data):
    """
    显示股票市场信息表格
    """
    plt.rcParams["font.sans-serif"] = ["AR PL UKai CN"]
    # plt.rcParams["font.sans-serif"] = ["Unifont"]  # 设置字体
    # plt.rcParams["font.sans-serif"] = ["SimHei"]  # 设置字体
    plt.rcParams["axes.unicode_minus"] = False  # 正常显示负号
    table = pd.DataFrame(data)
    fig, ax = plt.subplots()
    table = table.set_index("代码")
    Table(table)
    plt.title("我的胡萝卜")
    plt.savefig("figs/stock_table.png", dpi=460)
    plt.close()
    with open("figs/stock_table.png", "rb") as image_file:
        image_data = image_file.read()
    return base64.b64encode(image_data)


async def showStockInfoMe(websocket, user_id: int, group_id: int, message_id: int):
    """
    获取的我的股票信息
    """
    stockDb = StockTradingDB()
    records = stockDb.get_user_records(user_id, group_id)
    if not records:
        return "没有股票信息"
    data_list = []
    for record in records:
        data_list.append(
            {
                "代码": record["stock_id"],
                "买均": record["buy_avg_price"],
                "买总": record["buy_total_quantity"],
                "买总金": record["buy_total_cost"],
                "卖均": record["sell_avg_price"],
                "卖总": record["sell_total_quantity"],
                "卖总金": record["sell_total_amount"],
                "持仓": record["current_quantity"],
                "持均": record["current_avg_price"],
            }
        )
    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": message_id}},
            ],
        },
    }
    payload["params"]["message"].append(
        {
            "type": "image",
            "data": {
                "file": "base64://" + ShowStockMarketByBase64(data_list).decode("utf-8")
            },
        }
    )
    await websocket.send(json.dumps(payload))


# print(sellStock(3070004098, 765698568, "600519.SH", 1))

from function.group_operation import ReplySay


class CarrotMarketApplication(GroupMessageApplication):
    def __init__(
        self,
    ):
        applicationInfo = ApplicationInfo(
            "胡萝卜市场",
            "#carrotbuy# 买入股票代码 买入数量; #carrotsell# 卖出股票代码 卖出数量; #carrotme# 查询持仓",
        )
        super().__init__(applicationInfo, 75, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMesssageInfo):
        user_id = message.senderId
        group_id = message.groupId
        websocket = message.websocket
        message_id = message.messageId
        if message.painTextMessage.startswith("#carrotbuy#"):

            tmpMessage = message.painTextMessage.replace("#carrotbuy#", "")
            match buyStock(
                user_id,
                group_id,
                tmpMessage.split(" ")[0],
                float(tmpMessage.split(" ")[1]),  # type: ignore
            ):
                case BuyError.STOCK_NOT_FOUND:
                    await ReplySay(
                        websocket,
                        group_id,
                        message_id,
                        "胡萝卜代码未找到喵,比如600519.SH喵。",
                    )
                case BuyError.NOT_ENOUGH_POINT:
                    await ReplySay(
                        websocket,
                        group_id,
                        message_id,
                        "积分不足喵。",
                    )
                case BuyError.BUY_SUCCESS:
                    await ReplySay(
                        websocket,
                        group_id,
                        message_id,
                        "购买成功喵。",
                    )
        elif message.painTextMessage.startswith("#carrotsell#"):

            tmpMessage = message.painTextMessage.replace("#carrotsell#", "")
            match sellStock(
                user_id,
                group_id,
                tmpMessage.split(" ")[0],
                float(tmpMessage.split(" ")[1]),  # type: ignore
            ):
                case SellError.STOCK_NOT_FOUND:
                    await ReplySay(
                        websocket,
                        group_id,
                        message_id,
                        "胡萝卜代码未找到喵,比如600519.SH喵。",
                    )
                case SellError.NOT_ENOUGH_STOCK:
                    await ReplySay(
                        websocket,
                        group_id,
                        message_id,
                        "积分不足喵。",
                    )
                case SellError.SELL_SUCCESS:
                    await ReplySay(
                        websocket,
                        group_id,
                        message_id,
                        "出售成功喵。",
                    )
        elif message.painTextMessage.startswith("#carrotme#"):

            await showStockInfoMe(websocket, user_id, group_id, message_id)

    def judge(self, message: GroupMesssageInfo) -> bool:
        """判断消息是否为胡萝卜市场相关指令"""
        return (
            message.painTextMessage.startswith("#carrotbuy#")
            or message.painTextMessage.startswith("#carrotsell#")
            or message.painTextMessage.startswith("#carrotme#")
        )
