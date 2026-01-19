"""
数据库模块
提供异步数据库连接池和相关操作
"""
from database.db_pool import bot_db_pool, intel_db_pool, init_pools, close_pools

__all__ = ['bot_db_pool', 'intel_db_pool', 'init_pools', 'close_pools']
