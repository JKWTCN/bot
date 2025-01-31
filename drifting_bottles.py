import re
import sqlite3
import logging
import uuid
import time

from group_operate import GetGroupName
from tools import HasKeyWords, ReplySay, say, say_and_echo, timestamp_to_date
from Class.Group_member import get_user_name


# 丢漂流瓶
async def throw_drifting_bottles(
    websocket, user_id: int, group_id: int, message_id: int, text: str
):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    uid = str(uuid.uuid4())
    try:
        cur.execute(
            "INSERT INTO drifting_bottles (uuid,user_id,group_id,text,pick_times,time)VALUES (?,?,?,?,?,?);",
            (uid, user_id, group_id, text, 0, time.time()),
        )
        conn.commit()
    except sqlite3.OperationalError:
        logging.info("数据库表不存在,正在创建表drifting_bottles")
        cur.execute(
            "CREATE TABLE drifting_bottles (uuid TEXT, user_id INTEGER, group_id INTEGER, text TEXT, pick_times INTEGER, time INTEGER); "
        )
        conn.commit()
        cur.execute(
            "INSERT INTO drifting_bottles (uuid,user_id,group_id,text,pick_times,time)VALUES (?,?,?,?,?,?);",
            (uid, user_id, group_id, text, 0, time.time()),
        )
        conn.commit()
    conn.close()
    await say_and_echo(
        websocket,
        group_id,
        f"{get_user_name(user_id,group_id)},成功丢出了一个漂流瓶,标识ID为:{uid}",
        f"bottles|{message_id}|{user_id}|{group_id}",
    )


# 随机捞漂流瓶
async def pick_drifting_bottles_radom(websocket, user_id: int, group_id: int):
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
        await say(
            websocket,
            group_id,
            f"{get_user_name(user_id,group_id)},没有漂流瓶了喵，待会再来吧喵。",
        )
        return
    row = cur.fetchone()
    if row is None:
        await say(
            websocket,
            group_id,
            f"{get_user_name(user_id,group_id)},没有漂流瓶了喵，待会再来吧喵。",
        )
        return
    else:
        text = f"捞到了一个{get_user_name(row[1],row[2])}于{timestamp_to_date(row[5])}在{GetGroupName(row[2])}丢的漂流瓶,标识ID为:{row[0]}。\n{row[3]}"
        # user_id, group_id, text, time
        all_comment = load_comment(row[0])
        for comment in all_comment:
            text = (
                text
                + f"\n{timestamp_to_date(comment[3])}({GetGroupName(comment[1])}){get_user_name(comment[0],comment[1])}:{comment[2]}"
            )
        await say_and_echo(
            websocket,
            group_id,
            text,
            f"bottles|{row[0]}|{user_id}|{group_id}",
        )
        cur.execute(
            "UPDATE drifting_bottles SET pick_times = pick_times + 1 WHERE uuid = ?;",
            (row[0],),
        )
        conn.commit()


# 写入评论
def dump_comment(uuid: str, user_id: int, group_id: int, text: str):
    matches = re.search(r"\[(.*?)\]\[(.*?)\]\s*(.*)", text)
    if matches:
        text = matches.group(3)
    else:
        matches = re.search(r"\[(.*?)\]\s*(.*)", text)
        if matches:
            text = matches.group(2)
        else:
            return
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO drifting_bottles_comments (user_id,group_id,text,time,uuid)VALUES (?,?,?,?,?);",
            (user_id, group_id, text, time.time(), uuid),
        )
        conn.commit()
    except sqlite3.OperationalError:
        logging.info("数据库表不存在,正在创建表drifting_bottles_comments")
        cur.execute(
            "CREATE TABLE drifting_bottles_comments(user_id INTEGER, group_id INTEGER, text TEXT, time INTEGER,uuid TEXT); "
        )
        conn.commit()
        cur.execute(
            "INSERT INTO drifting_bottles_comments (user_id,group_id,text,time)VALUES (?,?,?,?,?);",
            (user_id, group_id, text, time.time(), uuid),
        )
        conn.commit()
    conn.close()


# 读取评论
def load_comment(uuid: str):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT user_id, group_id, text, time FROM drifting_bottles_comments where uuid = ?; ",
            (uuid,),
        )
    except sqlite3.OperationalError:
        logging.info("数据库表不存在,正在创建表drifting_bottles_comments")
        cur.execute(
            "CREATE TABLE drifting_bottles_comments(user_id INTEGER, group_id INTEGER, text TEXT, time INTEGER,uuid TEXT); "
        )
        conn.commit()
        cur.execute(
            "SELECT user_id, group_id, text, time FROM drifting_bottles_comments where uuid = ?; ",
            (uuid,),
        )
    all = cur.fetchall()
    conn.close()
    if len(all) == 0:
        return []
    else:
        return all


# 漂流瓶消息ID写入数据库，方便评论
def write_bottles_uuid_message_id(message_id: int, uuid: str, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO bottles_uuid_message_id (message_id,uuid,group_id)VALUES (?,?,?);",
            (message_id, uuid, group_id),
        )
        conn.commit()
    except sqlite3.OperationalError:
        logging.info("数据库表不存在,正在创建表bottles_uuid_message_id")
        cur.execute(
            "CREATE TABLE bottles_uuid_message_id ( message_id   INTEGER, uuid   TEXT, group_id   INTEGER ); "
        )
        conn.commit()
        cur.execute(
            "INSERT INTO bottles_uuid_message_id (message_id,uuid,group_id)VALUES (?,?,?);",
            (message_id, uuid, group_id),
        )
        conn.commit()
    conn.close()


# 判断是否为评论并写入
async def is_comment_write(websocket, user_id: int, group_id: int, raw_message: str):
    match = re.search(r"\[CQ:reply,id=(\d+)\]", raw_message)
    if match:
        message_id = match.group(1)
        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT uuid FROM bottles_uuid_message_id where message_id=? and group_id=?",
                (message_id, group_id),
            )
        except sqlite3.OperationalError:
            logging.info("数据库表不存在,正在创建表bottles_uuid_message_id")
            cur.execute(
                "CREATE TABLE bottles_uuid_message_id ( message_id   INTEGER, uuid   TEXT, group_id   INTEGER ); "
            )
            conn.commit()
            cur.execute(
                "SELECT uuid FROM bottles_uuid_message_id where message_id=? and group_id=?",
                (message_id, group_id),
            )
        a = cur.fetchone()
        if a == None:
            return False
        else:
            if len(a) > 0:
                uuid = a[0]
                if not HasKeyWords(raw_message, ["[CQ:image"]):
                    dump_comment(uuid, user_id, group_id, raw_message)
                    await ReplySay(
                        websocket,
                        group_id,
                        message_id,
                        f"评论ID为{uuid}的漂流瓶成功喵!",
                    )
                    return True
                else:
                    return False
    else:
        return False


# TODO uuid捞漂流瓶

# TODO 漂流瓶列表

# TODO 漂流瓶详情

# TODO 删除漂流瓶
