-- ============================================
-- bot_intelligence.db 索引优化
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
