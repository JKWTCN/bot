import sqlite3


def GetGroupName(group_id: int) -> int:
    """获取群聊名称

    Args:
        group_id (int): 群聊id

    Returns:
        _type_: 群聊的名称_description_
    """
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT group_name FROM group_info where group_id=?;",
        (group_id,),
    )
    data = cur.fetchall()
    if len(data) == 0:
        return group_id
    else:
        return int(data[0][0])
