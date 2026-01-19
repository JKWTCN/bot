"""
异步数据库群组操作模块
使用连接池提供高性能异步数据库访问
"""
from database.db_pool import bot_db_pool


async def GetGroupName(group_id: int) -> str:
    """
    获取群聊名称

    性能优化:
    - 使用连接池复用连接
    - 异步查询不阻塞

    Args:
        group_id: 群聊ID

    Returns:
        群聊名称
    """
    result = await bot_db_pool.fetchone(
        "SELECT group_name FROM group_info WHERE group_id = ?",
        (group_id,)
    )

    if result is None:
        return str(group_id)
    return str(result[0])


async def GetAllGroupMemberId(groupId: int) -> list:
    """
    获取群聊所有成员的用户ID

    Args:
        groupId: 群聊ID

    Returns:
        群聊所有成员的用户ID列表
    """
    rows = await bot_db_pool.fetchall(
        "SELECT user_id FROM group_member_info WHERE group_id = ?",
        (groupId,)
    )
    return [item[0] for item in rows]


async def GetAllGroupId() -> list:
    """
    获取所有群聊ID

    Returns:
        所有群聊ID列表
    """
    rows = await bot_db_pool.fetchall(
        "SELECT group_id FROM group_info"
    )
    return [item[0] for item in rows]
