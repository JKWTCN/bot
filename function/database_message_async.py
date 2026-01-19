"""
异步数据库操作模块
使用连接池提供高性能异步数据库访问
"""
import hashlib
import logging
from database.db_pool import bot_db_pool


async def GetChatContext(user_id: int, group_id: int, limit: int = 10) -> list:
    """
    从数据库中获取最近的聊天记录作为上下文

    性能优化:
    - 使用连接池复用连接
    - 异步执行不阻塞事件循环
    - 使用索引加速查询

    Args:
        user_id: 用户ID
        group_id: 群组ID
        limit: 消息数量限制

    Returns:
        上下文消息列表
    """
    rows = await bot_db_pool.fetchall(
        """SELECT sender_nickname, raw_message
           FROM group_message
           WHERE group_id = ? AND user_id = ?
           AND time >= strftime('%s','now','-30 minutes')
           ORDER BY time DESC
           LIMIT ?""",
        (group_id, user_id, limit)
    )

    # 将消息转换为适合模型输入的格式
    context_messages = []
    for nickname, message in reversed(rows):
        role = "assistant" if nickname == "乐可" else "user"
        context_messages.append({"role": role, "content": message})

    return context_messages


async def write_message(message: dict, text_message: str):
    """
    将消息写入数据库

    性能优化:
    - 使用连接池复用连接
    - 异步写入不阻塞
    - 自动提交事务

    Args:
        message: 消息字典
        text_message: 文本消息内容
    """
    try:
        sender = message["sender"]
        sender_name = sender["card"]
        if len(sender["card"]) == 0:
            sender_name = sender["nickname"]

        md5_hash = hashlib.md5(text_message.encode("utf-8")).hexdigest()

        await bot_db_pool.execute(
            """INSERT INTO group_message
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                message["time"],
                message["user_id"],
                sender_name,
                text_message,
                message["group_id"],
                message["self_id"],
                message["sub_type"],
                message["message_id"],
                md5_hash,
            )
        )
    except Exception as e:
        logging.error(f"写入消息失败: {e}")


async def get_md5_info(user_id: int, group_id: int, raw_message: str):
    """
    获取消息MD5信息

    性能优化:
    - 使用连接池
    - 使用索引加速查询
    - 一次连接执行多个查询

    Args:
        user_id: 用户ID
        group_id: 群组ID
        raw_message: 原始消息

    Returns:
        (md5_all_count, md5_user_count, last_message_id, last_message_time)
    """
    md5_hash = hashlib.md5(raw_message.encode("utf-8")).hexdigest()

    async with bot_db_pool.acquire() as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM group_message WHERE group_id = ? AND md5 = ?",
            (group_id, md5_hash)
        )
        md5_all_count = (await cursor.fetchone())[0]

        cursor = await conn.execute(
            "SELECT COUNT(*) FROM group_message WHERE user_id = ? AND group_id = ? AND md5 = ?",
            (user_id, group_id, md5_hash)
        )
        md5_user_count = (await cursor.fetchone())[0]

        cursor = await conn.execute(
            """SELECT message_id, time FROM group_message
               WHERE group_id = ? AND md5 = ?
               ORDER BY rowid DESC LIMIT 1 OFFSET 1""",
            (group_id, md5_hash)
        )
        last_message = await cursor.fetchone()
        last_message_id = last_message[0] if last_message else None
        last_message_time = last_message[1] if last_message else None

    return md5_all_count, md5_user_count, last_message_id, last_message_time


async def getImageInfo(websocket, group_id: int, message_id: int, need_replay_message_id: int):
    """
    获取图片信息

    Args:
        websocket: WebSocket连接
        group_id: 群组ID
        message_id: 消息ID
        need_replay_message_id: 需要回复的消息ID

    Returns:
        图片信息字符串
    """
    from function.GroupConfig import get_config
    from function.say import ReplySay

    try:
        result = await bot_db_pool.fetchone(
            "SELECT raw_message FROM group_message WHERE message_id = ?",
            (message_id,)
        )

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

    except Exception as e:
        logging.error(f"获取图片信息失败: {e}")
        return None
