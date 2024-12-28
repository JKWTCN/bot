import sqlite3
import logging
import uuid
import time

from group_operate import GetGroupName
from tools import say
from Class.Group_member import get_user_name


# 丢漂流瓶
async def throw_drifting_bottles(websocket, user_id: int, group_id: int, text: str):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    uid = uuid.uuid4()
    try:
        cur.execute(
            "INSERT INTO drifting_bottles (uuid,user_id,group_id,text,pick_times,time)VALUES (?,?,?,?,?,?);",
            (uid, user_id, group_id, text, 0, time.time()),
        )
    except sqlite3.OperationalError:
        logging.info("数据库表不存在,正在创建表drifting_bottles")
        cur.execute(
            "CREATE TABLE drifting_bottles ( uuid   TEXT, user_id    INTEGER, group_id   INTEGER, text   TEXT, pick_times INTEGER, time  INTEGER ); "
        )
        conn.commit()
        cur.execute(
            "INSERT INTO drifting_bottles (uuid,user_id,group_id,text,pick_times,time)VALUES (?,?,?,?,?,?);",
            (uid, user_id, group_id, text, 0, time.time()),
        )
        conn.commit()
    cur.close()
    await say(
        websocket,
        f"{get_user_name(user_id,group_id)},在群{GetGroupName(group_id)}中成功丢出了一个漂流瓶,标识ID为:{uid}",
    )


# 随机捞漂流瓶
async def pick_drifting_bottles_radom(websocket, user_id: int, group_id: int, text: str):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM drifting_bottles ORDER BY RANDOM() LIMIT 1;")
    except sqlite3.OperationalError:
        logging.info("数据库表不存在,正在创建表drifting_bottles")
        cur.execute(
            "CREATE TABLE drifting_bottles ( uuid   TEXT, user_id    INTEGER, group_id   INTEGER, text   TEXT, pick_times INTEGER, time  INTEGER ); "
        )
        conn.commit()
        say(websocket, "没有漂流瓶了喵，待会再来吧喵。")
        return
    row = cur.fetchone()
    if row is None:
        say(websocket, "没有漂流瓶了喵，待会再来吧喵。")
        return
    else:
        await say(
            websocket,
            f"{get_user_name(user_id,group_id)}捞到了一个{get_user_name(row[1],row[2])}在{GetGroupName(row[2])}丢的漂流瓶,标识ID为:{row[0]},内容为:{row[3]}",
        )
        cur.execute(
            "UPDATE drifting_bottles SET pick_times = pick_times + 1 WHERE uuid = ?;",
            (row[0],),
        )
        conn.commit()


# TODO 漂流瓶消息ID写入数据库，方便评论

# TODO uuid捞漂流瓶

# TODO 评论漂流瓶

# TODO 漂流瓶列表

# TODO 漂流瓶详情

# TODO 删除漂流瓶
