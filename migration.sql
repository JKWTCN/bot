-- 智能聊天系统数据库迁移脚本
-- 执行方式: sqlite3 bot.db < migration.sql

-- 用户画像表
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
);

-- 长期记忆表
CREATE TABLE IF NOT EXISTS long_term_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    memory_type TEXT,
    content TEXT,
    keywords TEXT,
    importance_score REAL DEFAULT 0.5,
    is_global BOOLEAN DEFAULT 1,
    created_at INTEGER,
    last_accessed_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_memory_user ON long_term_memory(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_importance ON long_term_memory(importance_score DESC);

-- 对话摘要表
CREATE TABLE IF NOT EXISTS conversation_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    group_id INTEGER,
    summary_text TEXT,
    key_topics TEXT,
    message_count INTEGER,
    start_time INTEGER,
    end_time INTEGER,
    created_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_summary_user ON conversation_summary(user_id, end_time DESC);
