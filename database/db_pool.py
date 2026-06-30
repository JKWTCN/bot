"""
数据库连接池管理
使用 aiosqlite 实现异步连接池
"""
import aiosqlite
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator


class DatabasePool:
    """异步数据库连接池"""

    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._pool: asyncio.Queue = None
        self._connections: set[aiosqlite.Connection] = set()
        self._checked_out: set[aiosqlite.Connection] = set()
        self._initialized = False
        self._closing = False

    async def init(self):
        """初始化连接池"""
        if self._initialized:
            return

        self._pool = asyncio.Queue(maxsize=self.pool_size)
        self._connections.clear()
        self._checked_out.clear()
        self._closing = False
        for _ in range(self.pool_size):
            conn = await aiosqlite.connect(self.db_path)
            # 启用 WAL 模式提升并发性能
            await conn.execute("PRAGMA journal_mode=WAL")
            # 设置繁忙超时时间为 30 秒
            await conn.execute("PRAGMA busy_timeout=30000")
            # 优化性能
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA cache_size=-10000")  # 10MB 缓存
            await conn.commit()
            self._connections.add(conn)
            await self._pool.put(conn)
        self._initialized = True
        print(f"✓ 数据库连接池已初始化: {self.db_path} (size={self.pool_size}) [WAL模式已启用]")

    @asynccontextmanager
    async def acquire(self, timeout: float = 30.0) -> AsyncIterator[aiosqlite.Connection]:
        """获取连接，带超时保护"""
        if not self._initialized:
            await self.init()
        if self._closing:
            raise RuntimeError(f"数据库连接池正在关闭: {self.db_path}")

        try:
            conn = await asyncio.wait_for(self._pool.get(), timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"获取数据库连接超时 ({timeout}秒)")

        self._checked_out.add(conn)
        try:
            yield conn
        finally:
            self._checked_out.discard(conn)
            if self._closing:
                await self._close_connection(conn)
            else:
                await self._pool.put(conn)

    async def close_all(self, timeout: float = 5.0):
        """关闭所有连接"""
        if not self._initialized:
            return

        self._closing = True
        deadline = asyncio.get_running_loop().time() + timeout
        while self._checked_out and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.05)

        if self._checked_out:
            logging.warning(
                "关闭数据库连接池时仍有连接未归还: %s count=%s",
                self.db_path,
                len(self._checked_out),
            )

        while self._pool is not None and not self._pool.empty():
            try:
                self._pool.get_nowait()
            except asyncio.QueueEmpty:
                break

        await asyncio.gather(
            *(self._close_connection(conn) for conn in list(self._connections)),
            return_exceptions=True,
        )
        self._connections.clear()
        self._checked_out.clear()
        self._initialized = False
        self._closing = False
        print(f"✓ 数据库连接池已关闭: {self.db_path}")

    async def _close_connection(self, conn: aiosqlite.Connection):
        """关闭单个连接并吞掉关闭期异常。"""
        try:
            await conn.close()
        except Exception as e:
            logging.warning("关闭数据库连接失败: %s error=%s", self.db_path, e)

    async def execute(self, sql: str, params=()):
        """便捷执行方法"""
        async with self.acquire() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()
            return cursor

    async def executemany(self, sql: str, params_list):
        """批量执行"""
        async with self.acquire() as conn:
            await conn.executemany(sql, params_list)
            await conn.commit()

    async def fetchone(self, sql: str, params=()):
        """查询单条"""
        async with self.acquire() as conn:
            cursor = await conn.execute(sql, params)
            return await cursor.fetchone()

    async def fetchall(self, sql: str, params=()):
        """查询多条"""
        async with self.acquire() as conn:
            cursor = await conn.execute(sql, params)
            return await cursor.fetchall()


# 全局单例
bot_db_pool = DatabasePool("bot.db", pool_size=10)
intel_db_pool = DatabasePool("bot_intelligence.db", pool_size=5)


async def init_pools():
    """初始化所有连接池"""
    await bot_db_pool.init()
    await intel_db_pool.init()


async def close_pools():
    """关闭所有连接池"""
    await bot_db_pool.close_all()
    await intel_db_pool.close_all()
