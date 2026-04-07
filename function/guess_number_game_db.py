"""
猜数字游戏数据库操作模块
使用独立数据库文件 db/guess_number_game.db

功能：
- 游戏状态管理
- 猜测记录管理
- 参与者查询
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = "db/guess_number_game.db"


def init_db():
    """初始化数据库和表结构"""
    # 确保 db 目录存在
    if not os.path.exists("db"):
        os.makedirs("db")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 创建游戏状态表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guess_number_game (
            group_id INTEGER PRIMARY KEY,
            target_number INTEGER,
            is_active INTEGER DEFAULT 0,
            guess_count INTEGER DEFAULT 0,
            start_time NUMERIC,
            starter_id INTEGER
        )
    """)

    # 创建猜测记录表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guess_number_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            guess_number INTEGER,
            result TEXT,
            guess_time NUMERIC
        )
    """)

    # 创建索引以提高查询性能
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_guess_records_group
        ON guess_number_records(group_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_guess_records_user
        ON guess_number_records(user_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_guess_records_time
        ON guess_number_records(guess_time)
    """)

    conn.commit()
    conn.close()


def start_game(group_id: int, starter_id: int, target_number: int) -> bool:
    """
    开始新游戏

    Args:
        group_id: 群组ID
        starter_id: 发起人ID
        target_number: 目标数字

    Returns:
        bool: 成功返回True，游戏已存在返回False
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO guess_number_game
            (group_id, target_number, is_active, guess_count, start_time, starter_id)
            VALUES (?, ?, 1, 0, ?, ?)
        """, (group_id, target_number, datetime.now().timestamp(), starter_id))

        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # 游戏已存在
        return False
    finally:
        conn.close()


def get_game_status(group_id: int) -> dict:
    """
    获取游戏状态

    Args:
        group_id: 群组ID

    Returns:
        dict: 游戏状态信息，如果游戏不存在返回None
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT target_number, is_active, guess_count, start_time, starter_id
        FROM guess_number_game WHERE group_id = ?
    """, (group_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "target_number": row[0],
            "is_active": bool(row[1]),
            "guess_count": row[2],
            "start_time": row[3],
            "starter_id": row[4]
        }
    return None


def make_guess(group_id: int, user_id: int, guess: int) -> dict:
    """
    进行猜测

    Args:
        group_id: 群组ID
        user_id: 用户ID
        guess: 猜测的数字

    Returns:
        dict: 包含猜测结果的字典
              - success: 是否成功
              - result: 结果（"大了"/"小了"/"正确"）
              - target: 目标数字（仅当正确时）
              - guess_count: 当前猜测次数
    """
    status = get_game_status(group_id)
    if not status or not status["is_active"]:
        return {"success": False, "message": "游戏未激活"}

    target = status["target_number"]

    # 判断结果
    if guess == target:
        result = "正确"
    elif guess > target:
        result = "大了"
    else:
        result = "小了"

    # 记录猜测
    record_guess(group_id, user_id, guess, result)

    # 更新猜测次数
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE guess_number_game SET guess_count = guess_count + 1
        WHERE group_id = ?
    """, (group_id,))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "result": result,
        "target": target if result == "正确" else None,
        "guess_count": status["guess_count"] + 1
    }


def record_guess(group_id: int, user_id: int, guess: int, result: str):
    """
    记录猜测到数据库

    Args:
        group_id: 群组ID
        user_id: 用户ID
        guess: 猜测的数字
        result: 结果（"大了"/"小了"/"正确"）
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO guess_number_records
        (group_id, user_id, guess_number, result, guess_time)
        VALUES (?, ?, ?, ?, ?)
    """, (group_id, user_id, guess, result, datetime.now().timestamp()))

    conn.commit()
    conn.close()


def end_game(group_id: int):
    """
    结束游戏（设置为非激活状态）

    Args:
        group_id: 群组ID
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE guess_number_game SET is_active = 0 WHERE group_id = ?
    """, (group_id,))

    conn.commit()
    conn.close()


def get_guess_records(group_id: int, limit: int = 5) -> list:
    """
    获取最近的猜测记录

    Args:
        group_id: 群组ID
        limit: 返回记录数量

    Returns:
        list: 猜测记录列表
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id, guess_number, result, guess_time
        FROM guess_number_records
        WHERE group_id = ?
        ORDER BY guess_time DESC
        LIMIT ?
    """, (group_id, limit))

    rows = cursor.fetchall()
    conn.close()

    return [{"user_id": r[0], "guess": r[1], "result": r[2], "time": r[3]} for r in rows]


def get_participants(group_id: int) -> list:
    """
    获取游戏的所有参与者（去重）

    Args:
        group_id: 群组ID

    Returns:
        list: 参与者ID列表
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT user_id
        FROM guess_number_records
        WHERE group_id = ?
    """, (group_id,))

    rows = cursor.fetchall()
    conn.close()

    return [r[0] for r in rows]


def clear_game_records(group_id: int):
    """
    清除游戏记录（用于重新开始游戏）

    Args:
        group_id: 群组ID
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 删除猜测记录
    cursor.execute("""
        DELETE FROM guess_number_records WHERE group_id = ?
    """, (group_id,))

    # 删除游戏状态
    cursor.execute("""
        DELETE FROM guess_number_game WHERE group_id = ?
    """, (group_id,))

    conn.commit()
    conn.close()


# 初始化数据库
init_db()
