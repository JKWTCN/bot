import sqlite3
import logging


# 获取积分等级
def get_level(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT level FROM level where user_id=? and group_id=?;",
            (user_id, group_id),
        )
    except sqlite3.OperationalError:
        logging.info("数据库表不存在,level")
        cur.execute(
            "CREATE TABLE level ( user_id  INTEGER, group_id INTEGER, level INTEGER ); "
        )
        conn.commit()
        cur.execute(
            "SELECT level FROM level where user_id=? and group_id=?;",
            (user_id, group_id),
        )
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO level (user_id,group_id,level ) VALUES (?,?,?);",
            (user_id, group_id, 0),
        )
        conn.commit()
        conn.close()
        return 0
    else:
        return data[0][0]


# 设置积分等级
def set_level(user_id: int, group_id: int, level: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE level SET level=? where user_id=? and group_id=?",
        (
            level,
            user_id,
            group_id,
        ),
    )
    conn.commit()
