import logging
import re
import sqlite3
import requests
from function.say import ReplySay


def GetChatContext(user_id: int, group_id: int, limit: int = 5) -> list:
    """从数据库中获取最近的聊天记录作为上下文"""
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()

    # 获取最近的几条聊天记录(包括用户和机器人的消息)
    cursor.execute(
        """
        SELECT sender_nickname, raw_message 
        FROM group_message 
        WHERE group_id = ? AND user_id = ? 
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



