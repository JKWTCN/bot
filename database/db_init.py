"""
数据库初始化和优化配置
确保所有数据库连接都使用 WAL 模式和优化配置
"""
import sqlite3
import os


def init_database_wal(db_path: str = "bot.db") -> None:
    """
    初始化数据库，启用 WAL 模式和优化配置

    WAL (Write-Ahead Logging) 模式优势：
    1. 允许并发读写（读操作不会被写操作阻塞）
    2. 写操作更快（不需要写入两个文件）
    3. 更好的并发性能
    4. 减少磁盘 I/O

    Args:
        db_path: 数据库文件路径
    """
    if not os.path.exists(db_path):
        # 如果数据库不存在，创建一个空文件
        open(db_path, 'a').close()

    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()

    try:
        # 启用 WAL 模式（最重要）
        cursor.execute("PRAGMA journal_mode=WAL")

        # 设置繁忙超时时间为 30 秒
        cursor.execute("PRAGMA busy_timeout=30000")

        # 优化同步模式（NORMAL 在性能和安全性之间取得平衡）
        cursor.execute("PRAGMA synchronous=NORMAL")

        # 设置缓存大小（负值表示 KB，-10000 = 10MB）
        cursor.execute("PRAGMA cache_size=-10000")

        # 设置临时存储在内存中
        cursor.execute("PRAGMA temp_store=MEMORY")

        # 设置 mmap 大小（提升大数据库性能）
        cursor.execute("PRAGMA mmap_size=30000000000")

        # 优化页面大小（通常 4096 是最佳选择）
        cursor.execute("PRAGMA page_size=4096")

        conn.commit()

        # 验证 WAL 模式是否启用
        cursor.execute("PRAGMA journal_mode")
        journal_mode = cursor.fetchone()[0]
        print(f"✓ 数据库已初始化: {db_path} [WAL模式: {journal_mode}]")

    except Exception as e:
        print(f"✗ 数据库初始化失败: {db_path}, 错误: {e}")
        conn.rollback()
    finally:
        conn.close()


def init_all_databases():
    """初始化所有数据库文件"""
    databases = [
        "bot.db",
        "bot_intelligence.db",
    ]

    for db_path in databases:
        if os.path.exists(db_path) or os.path.basename(db_path) in ["bot.db", "bot_intelligence.db"]:
            init_database_wal(db_path)


if __name__ == "__main__":
    # 测试初始化
    init_all_databases()
