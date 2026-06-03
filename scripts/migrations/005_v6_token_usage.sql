-- Migration 005: V6 Token Usage Tracking
-- Created: 2026-06-03
-- 补充token_usage表的索引

CREATE INDEX IF NOT EXISTS idx_token_usage_role ON token_usage(role);
CREATE INDEX IF NOT EXISTS idx_token_usage_chapter ON token_usage(chapter_index);
