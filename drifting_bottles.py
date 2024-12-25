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


# TODO 随机捞漂流瓶
# TODO uuid捞漂流瓶
# TODO 评论漂流瓶
# TODO 漂流瓶列表
# TODO 漂流瓶详情
# TODO 删除漂流瓶
