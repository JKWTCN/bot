import sqlite3
from tools import GetNowDay


# 发送水群积分
def SendRewards(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT all_num,today_num,today FROM chat_rewards where user_id=? and group_id=?;",
        (
            user_id,
            group_id,
        ),
    )
    data = cur.fetchall()
    if len(data) == 0:
        cur.execute(
            "INSERT INTO chat_rewards (user_id,group_id,all_num,today_num,today)\
                VALUES (?,?,?,?,?);",
            (user_id, group_id, 0, 0, GetNowDay()),
        )
        conn.commit()
        cur.execute(
            "SELECT all_num,today_num,today FROM chat_rewards where user_id=? and group_id=?;",
            (
                user_id,
                group_id,
            ),
        )
        data = cur.fetchall()
    all_num = data[0][0]
    today_num = data[0][1]
    today = data[0][2]
    all_num = all_num + 1
    if today != GetNowDay():
        today_num = 1
        today = GetNowDay()
    else:
        today_num = today_num + 1
    cur.execute(
        "UPDATE chat_rewards SET all_num = ?,today_num = ?,today = ?\
            WHERE user_id = ? AND group_id = ?;",
        (all_num, today_num, today, user_id, group_id),
    )
    conn.commit()
    return (all_num, today_num)
