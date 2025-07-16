import sqlite3


def GetGroupName(group_id: int) -> str:
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
        return str(group_id)
    else:
        return str(data[0][0])


def GetAllGroupMemberId(groupId: int) -> list:
    """获取群聊所有成员的用户ID

    Args:
        groupId (int): 群聊ID

    Returns:
        list: 群聊所有成员的用户ID列表
    """
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id FROM group_member_info where group_id=?;",
        (groupId,),
    )
    data = cur.fetchall()
    conn.close()
    return [item[0] for item in data]


def GetAllGroupId() -> list:
    """获取所有群聊ID

    Returns:
        list: 所有群聊ID列表
    """
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT group_id FROM group_info;",
    )
    data = cur.fetchall()
    conn.close()
    return [item[0] for item in data]
