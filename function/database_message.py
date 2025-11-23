import hashlib
import logging
import re
import sqlite3
import requests
from function.say import ReplySay
from function.GroupConfig import get_config


def incWhoAtMe(user_id: int, ated_id: int):
    """增加艾特信息"""
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    now_num = getWhoAtMe(user_id, ated_id)
    cur.execute(
        "UPDATE who_at_me SET nums = ? WHERE user_id = ? and ated_id=?;",
        (now_num + 1, user_id, ated_id),
    )
    conn.commit()
    conn.close()


def getWhoAtMe(user_id: int, ated_id: int):
    """查找艾特次数"""
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT nums FROM who_at_me where user_id=? and ated_id=? ;", (user_id, ated_id)
    )
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO who_at_me (user_id,nums,ated_id) VALUES (?,?,?);",
            (user_id, 0, ated_id),
        )
        conn.commit()
        conn.close()
        return 0
    else:
        conn.close()
        return data[0][0]


def GetChatContext(user_id: int, group_id: int, limit: int = 10) -> list:
    """从数据库中获取最近的聊天记录作为上下文"""
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()

    # 获取最近的几条聊天记录,并且时间限定在最近30分钟内;
    cursor.execute(
        """
        SELECT sender_nickname, raw_message 
        FROM group_message s
        WHERE group_id = ? AND user_id = ? AND time >= strftime('%s','now','-30 minutes')
        ORDER BY time DESC 
        LIMIT ?
    """,
        (
            group_id,
            user_id,
            limit,
        ),
    )

    messages = cursor.fetchall()
    conn.close()

    # 将消息转换为适合模型输入的格式
    context_messages = []
    for nickname, message in reversed(messages):
        role = "assistant" if nickname == "乐可" else "user"
        context_messages.append({"role": role, "content": message})

    return context_messages


def write_message(message: dict, text_messgae: str):
    """将消息写入数据库"""
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    try:
        sender = message["sender"]
        sender_name = sender["card"]
        if len(sender["card"]) == 0:
            sender_name = sender["nickname"]
        md5_hash = hashlib.md5(text_messgae.encode("utf-8")).hexdigest()
        cur.execute(
            "INSERT INTO group_message VALUES(?,?,?,?,?,?,?,?,?)",
            (
                message["time"],
                message["user_id"],
                sender_name,
                text_messgae,
                message["group_id"],
                message["self_id"],
                message["sub_type"],
                message["message_id"],
                md5_hash,
            ),
        )
        conn.commit()
    except:
        pass
    conn.close()


# 获取图片内容
async def getImageInfo(
    websocket, group_id: int, message_id: int, need_replay_message_id: int
):
    try:
        # 连接数据库
        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()
        # 执行查询
        cursor.execute(
            """
            SELECT raw_message 
            FROM group_message 
            WHERE message_id = ?
        """,
            (message_id,),
        )

        # 获取结果
        result = cursor.fetchone()

        if result:
            imageInfo = result[0]
            if imageInfo == "[图片]":
                if get_config("image_parsing", group_id):
                    await ReplySay(
                        websocket,
                        group_id,
                        need_replay_message_id,
                        "图片好像丢了喵,才不是乐可的疏忽喵,最好重新发送图片喵。",
                    )
                else:
                    await ReplySay(
                        websocket,
                        group_id,
                        need_replay_message_id,
                        "本群未开启图片解析功能喵。",
                    )
            else:
                await ReplySay(
                    websocket,
                    group_id,
                    need_replay_message_id,
                    imageInfo,
                )
        else:
            await ReplySay(
                websocket,
                group_id,
                need_replay_message_id,
                "此消息还在识别喵,请稍后再回复喵。",
            )

    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return None

    finally:
        # 确保连接被关闭
        if conn:
            conn.close()


def calculate_md5(text):
    md5_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
    return md5_hash


def get_md5_info(user_id: int, group_id: int, raw_message: str):
    md5_hash = calculate_md5(raw_message)
    # print(f"Calculated MD5: {md5_hash}")
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    # 查找数据库 group_message 表中对应该 md5 出现的次数
    cursor.execute(
        "SELECT COUNT(*) FROM group_message WHERE group_id = ? AND md5 = ?",
        (group_id, md5_hash),
    )
    md5_all_count = cursor.fetchone()[0]
    # 查找数据库 group_message 表中满足 user_id md5 出现的次数
    cursor.execute(
        "SELECT COUNT(*) FROM group_message WHERE user_id = ? AND group_id = ? AND md5 = ?",
        (user_id, group_id, md5_hash),
    )
    md5_user_count = cursor.fetchone()[0]
    # 查找数据库 group_message 表中倒数第二次该 md5 的 message_id 和 time
    cursor.execute(
        "SELECT message_id, time FROM group_message WHERE group_id = ? AND md5 = ? ORDER BY rowid DESC LIMIT 1 OFFSET 1",
        (group_id, md5_hash),
    )
    last_message = cursor.fetchone()
    last_message_id = last_message[0] if last_message else None
    last_message_time = last_message[1] if last_message else None
    conn.close()
    return md5_all_count, md5_user_count, last_message_id, last_message_time
