"""
数据库初始化和优化配置
确保所有数据库连接都使用 WAL 模式和优化配置
"""
import hashlib
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

    init_bot_schema("bot.db")
    init_intelligence_schema("bot_intelligence.db")


def init_bot_schema(db_path: str = "bot.db") -> None:
    """初始化聊天主库的基础表结构,兼容旧 8 列 group_message。"""
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS group_message (
                time INTEGER,
                user_id INTEGER,
                sender_nickname TEXT,
                raw_message TEXT,
                group_id INTEGER,
                self_id INTEGER,
                sub_type TEXT,
                message_id INTEGER,
                md5 TEXT
            )
            """
        )
        cursor.execute("PRAGMA table_info(group_message)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        if "md5" not in existing_columns:
            cursor.execute("ALTER TABLE group_message ADD COLUMN md5 TEXT")
            cursor.execute(
                """
                UPDATE group_message
                SET md5 = lower(hex(randomblob(16)))
                WHERE md5 IS NULL
                """
            )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_group_message_time
            ON group_message(group_id, time DESC)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_group_message_user_time
            ON group_message(user_id, group_id, time DESC)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_group_message_md5
            ON group_message(group_id, md5)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_group_message_id
            ON group_message(message_id)
            """
        )
        conn.commit()
        print(f"✓ 聊天主数据库结构已初始化: {db_path}")
    except Exception as e:
        conn.rollback()
        print(f"✗ 聊天主数据库结构初始化失败: {db_path}, 错误: {e}")
    finally:
        conn.close()


def init_intelligence_schema(db_path: str = "bot_intelligence.db") -> None:
    """初始化智能聊天扩展表结构,保持幂等。"""
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    try:
        _ensure_user_profile_table(cursor)
        _ensure_long_term_memory_columns(cursor)
        _ensure_memory_episode_table(cursor)
        _ensure_expression_learning_tables(cursor)
        _ensure_conversation_summary_table(cursor)
        _ensure_ai_chat_invocation_table(cursor)
        _backfill_memory_content_hash(cursor)
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_long_term_memory_dedupe
            ON long_term_memory(user_id, memory_type, content_hash)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_long_term_memory_context
            ON long_term_memory(context_type, context_id, updated_at DESC)
            """
        )
        conn.commit()
        print(f"✓ 智能聊天数据库结构已初始化: {db_path}")
    except Exception as e:
        conn.rollback()
        print(f"✗ 智能聊天数据库结构初始化失败: {db_path}, 错误: {e}")
    finally:
        conn.close()


def _ensure_user_profile_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_profile (
            user_id INTEGER PRIMARY KEY,
            nickname TEXT,
            interests TEXT,
            topics_preference TEXT,
            interaction_style TEXT,
            preferred_response_length TEXT DEFAULT 'medium',
            emoji_usage REAL DEFAULT 0.5,
            activity_level REAL DEFAULT 0.5,
            familiarity_level REAL DEFAULT 0.3,
            interaction_depth REAL DEFAULT 0.3,
            created_at INTEGER,
            updated_at INTEGER,
            last_interacted_at INTEGER
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_profile_last_interacted
        ON user_profile(last_interacted_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_profile_activity
        ON user_profile(activity_level DESC)
        """
    )


def _ensure_long_term_memory_columns(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS long_term_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            memory_type TEXT,
            content TEXT,
            keywords TEXT,
            importance_score REAL DEFAULT 0.5,
            is_global BOOLEAN DEFAULT 1,
            created_at INTEGER,
            last_accessed_at INTEGER,
            content_hash TEXT,
            context_type TEXT,
            context_id INTEGER,
            updated_at INTEGER,
            access_count INTEGER DEFAULT 0,
            title TEXT,
            content_vector TEXT,
            vector_version TEXT,
            source_message_id INTEGER,
            person_name TEXT,
            memory_scope TEXT DEFAULT 'person'
        )
        """
    )
    cursor.execute("PRAGMA table_info(long_term_memory)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    columns = {
        "content_hash": "TEXT",
        "context_type": "TEXT",
        "context_id": "INTEGER",
        "updated_at": "INTEGER",
        "access_count": "INTEGER DEFAULT 0",
        "title": "TEXT",
        "content_vector": "TEXT",
        "vector_version": "TEXT",
        "source_message_id": "INTEGER",
        "person_name": "TEXT",
        "memory_scope": "TEXT DEFAULT 'person'",
    }
    for column_name, column_type in columns.items():
        if column_name not in existing_columns:
            cursor.execute(f"ALTER TABLE long_term_memory ADD COLUMN {column_name} {column_type}")
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_long_term_memory_source_message
        ON long_term_memory(source_message_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_long_term_memory_person
        ON long_term_memory(person_name, updated_at DESC)
        """
    )


def _ensure_memory_episode_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_episode (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            person_name TEXT,
            title TEXT,
            summary TEXT,
            keywords TEXT,
            start_time INTEGER,
            end_time INTEGER,
            source_message_ids TEXT,
            content_vector TEXT,
            vector_version TEXT,
            created_at INTEGER,
            updated_at INTEGER,
            access_count INTEGER DEFAULT 0
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_memory_episode_group_time
        ON memory_episode(group_id, end_time DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_memory_episode_user_time
        ON memory_episode(user_id, end_time DESC)
        """
    )


def _ensure_expression_learning_tables(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS expression_style (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            style_key TEXT,
            style_value TEXT,
            example TEXT,
            weight REAL DEFAULT 1.0,
            created_at INTEGER,
            updated_at INTEGER,
            last_seen_at INTEGER,
            UNIQUE(group_id, user_id, style_key, style_value)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_expression_style_scope
        ON expression_style(group_id, user_id, style_key, weight DESC)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS group_jargon (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            phrase TEXT,
            example TEXT,
            count INTEGER DEFAULT 1,
            created_at INTEGER,
            updated_at INTEGER,
            last_seen_at INTEGER,
            UNIQUE(group_id, phrase)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_group_jargon_group_count
        ON group_jargon(group_id, count DESC, last_seen_at DESC)
        """
    )


def _ensure_conversation_summary_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            group_id INTEGER,
            summary_text TEXT,
            key_topics TEXT,
            key_entities TEXT,
            message_count INTEGER,
            start_time INTEGER,
            end_time INTEGER,
            created_at INTEGER
        )
        """
    )
    cursor.execute("PRAGMA table_info(conversation_summary)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if "key_entities" not in existing_columns:
        cursor.execute("ALTER TABLE conversation_summary ADD COLUMN key_entities TEXT")
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_summary_user
        ON conversation_summary(user_id, end_time DESC)
        """
    )


def _ensure_ai_chat_invocation_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_chat_invocation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at INTEGER,
            group_id INTEGER,
            user_id INTEGER,
            message_id INTEGER,
            stage TEXT,
            model_name TEXT,
            provider TEXT,
            prompt TEXT,
            response TEXT,
            success INTEGER DEFAULT 1,
            error TEXT,
            metadata TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_chat_invocation_message
        ON ai_chat_invocation(group_id, message_id, stage)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_chat_invocation_created
        ON ai_chat_invocation(created_at DESC)
        """
    )


def _backfill_memory_content_hash(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        SELECT id, user_id, memory_type, content
        FROM long_term_memory
        WHERE content IS NOT NULL AND TRIM(content) != ''
        ORDER BY id ASC
        """
    )
    rows = cursor.fetchall()
    seen_keys: set[tuple[int, str, str]] = set()
    for memory_id, user_id, memory_type, content in rows:
        content_hash = _memory_content_hash(str(content))
        key = (int(user_id or 0), str(memory_type or "fact"), content_hash)
        if key in seen_keys:
            cursor.execute(
                "UPDATE long_term_memory SET content_hash = NULL WHERE id = ?",
                (memory_id,),
            )
            continue
        seen_keys.add(key)
        cursor.execute(
            """
            UPDATE long_term_memory
            SET content_hash = ?,
                updated_at = COALESCE(updated_at, last_accessed_at, created_at),
                access_count = COALESCE(access_count, 0)
            WHERE id = ?
            """,
            (content_hash, memory_id),
        )


def _memory_content_hash(content: str) -> str:
    normalized = " ".join(content.strip().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    # 测试初始化
    init_all_databases()
