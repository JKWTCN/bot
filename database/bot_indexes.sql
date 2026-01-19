-- ============================================
-- bot.db 索引优化
-- ============================================

-- 群组消息查询 (按时间倒序)
CREATE INDEX IF NOT EXISTS idx_group_message_time
ON group_message(group_id, time DESC);

-- 用户消息查询
CREATE INDEX IF NOT EXISTS idx_group_message_user_time
ON group_message(user_id, group_id, time DESC);

-- MD5去重查询
CREATE INDEX IF NOT EXISTS idx_group_message_md5
ON group_message(group_id, md5);

-- 消息ID查询
CREATE INDEX IF NOT EXISTS idx_group_message_id
ON group_message(message_id);

-- 复合索引: 群组+时间+用户
CREATE INDEX IF NOT EXISTS idx_group_message_composite
ON group_message(group_id, time DESC, user_id);
