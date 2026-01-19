-- ============================================
-- 数据库索引优化
-- 目标: 提升查询性能 50-80%
-- ============================================

-- 主消息库索引
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

-- 智能数据库索引
-- ============================================

-- 用户画像: 按最后交互时间排序
CREATE INDEX IF NOT EXISTS idx_user_profile_last_interacted
ON user_profile(last_interacted_at DESC);

-- 用户画像: 按活跃度排序
CREATE INDEX IF NOT EXISTS idx_user_profile_activity
ON user_profile(activity_level DESC);

-- 长期记忆: 按用户+重要性+访问时间
CREATE INDEX IF NOT EXISTS idx_long_term_memory_user_importance
ON long_term_memory(user_id, importance_score DESC, last_accessed_at DESC);

-- 查看索引使用情况
-- ============================================

-- 检查索引是否生效
-- EXPLAIN QUERY PLAN
-- SELECT * FROM group_message
-- WHERE group_id = 123 AND time >= strftime('%s', 'now', '-30 minutes')
-- ORDER BY time DESC;
