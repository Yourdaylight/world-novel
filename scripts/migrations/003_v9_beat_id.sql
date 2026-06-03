-- Migration 003: V9 Beat ID Columns
-- Created: 2026-06-03
-- 为场景相关表添加beat_id字段

ALTER TABLE scene_turns ADD COLUMN beat_id TEXT DEFAULT '';
ALTER TABLE character_actions ADD COLUMN beat_id TEXT DEFAULT '';
ALTER TABLE scene_metadata ADD COLUMN beat_id TEXT DEFAULT '';
