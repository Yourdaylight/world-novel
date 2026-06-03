-- Migration 002: V6 Word Count Default
-- Created: 2026-06-03
-- 修复world_propositions的expected_word_count默认值

-- 添加列（如果不存在）
ALTER TABLE world_propositions ADD COLUMN expected_word_count INTEGER DEFAULT 1000000;

-- 迁移旧数据：将0值更新为默认值1000000
UPDATE world_propositions SET expected_word_count = 1000000
WHERE expected_word_count = 0 OR expected_word_count IS NULL;
