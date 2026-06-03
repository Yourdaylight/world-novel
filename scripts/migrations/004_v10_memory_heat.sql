-- Migration 004: V10 Memory Heat System
-- Created: 2026-06-03
-- 为episodic_memories添加热度评分字段

ALTER TABLE episodic_memories ADD COLUMN heat_score REAL DEFAULT 0.5;
ALTER TABLE episodic_memories ADD COLUMN last_accessed_chapter INTEGER DEFAULT 0;
ALTER TABLE episodic_memories ADD COLUMN access_count INTEGER DEFAULT 0;
ALTER TABLE episodic_memories ADD COLUMN consolidated INTEGER DEFAULT 0;
