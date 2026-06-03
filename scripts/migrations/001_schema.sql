-- Migration 001: Initial Schema
-- Created: 2026-06-03
-- 初始数据库Schema创建，包含所有基础表

-- 小说基本信息
CREATE TABLE IF NOT EXISTS novels (
    novel_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    world_description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'draft'
);

-- 世界三命题
CREATE TABLE IF NOT EXISTS world_propositions (
    novel_id TEXT PRIMARY KEY,
    proposition_1 TEXT DEFAULT '',
    proposition_2 TEXT DEFAULT '',
    proposition_3 TEXT DEFAULT '',
    expected_word_count INTEGER DEFAULT 1000000,
    FOREIGN KEY (novel_id) REFERENCES novels(novel_id)
);

-- 角色定义
CREATE TABLE IF NOT EXISTS characters (
    character_id TEXT PRIMARY KEY,
    novel_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    personality TEXT DEFAULT '',
    goals TEXT DEFAULT '',
    FOREIGN KEY (novel_id) REFERENCES novels(novel_id)
);

-- 角色关系
CREATE TABLE IF NOT EXISTS relationships (
    relationship_id TEXT PRIMARY KEY,
    novel_id TEXT NOT NULL,
    character_a_id TEXT NOT NULL,
    character_b_id TEXT NOT NULL,
    relationship_type TEXT DEFAULT '',
    strength REAL DEFAULT 0.0,
    FOREIGN KEY (novel_id) REFERENCES novels(novel_id),
    FOREIGN KEY (character_a_id) REFERENCES characters(character_id),
    FOREIGN KEY (character_b_id) REFERENCES characters(character_id)
);

-- 章节内容
CREATE TABLE IF NOT EXISTS chapters (
    chapter_id TEXT PRIMARY KEY,
    novel_id TEXT NOT NULL,
    chapter_index INTEGER NOT NULL,
    title TEXT DEFAULT '',
    content TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (novel_id) REFERENCES novels(novel_id)
);

-- Token使用记录
CREATE TABLE IF NOT EXISTS token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    chapter_index INTEGER DEFAULT -1,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    model TEXT DEFAULT '',
    description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 场景回合
CREATE TABLE IF NOT EXISTS scene_turns (
    turn_id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id TEXT NOT NULL,
    chapter_index INTEGER NOT NULL,
    turn_index INTEGER NOT NULL,
    character_id TEXT DEFAULT '',
    action TEXT DEFAULT '',
    thought TEXT DEFAULT '',
    dialogue TEXT DEFAULT '',
    target_id TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    beat_id TEXT DEFAULT ''
);

-- 角色行动
CREATE TABLE IF NOT EXISTS character_actions (
    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id TEXT NOT NULL,
    chapter_index INTEGER NOT NULL,
    character_id TEXT DEFAULT '',
    action TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    beat_id TEXT DEFAULT ''
);

-- 场景元数据
CREATE TABLE IF NOT EXISTS scene_metadata (
    metadata_id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id TEXT NOT NULL,
    chapter_index INTEGER NOT NULL,
    key TEXT DEFAULT '',
    value TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    beat_id TEXT DEFAULT ''
);

-- 情节记忆
CREATE TABLE IF NOT EXISTS episodic_memories (
    memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id TEXT NOT NULL,
    character_id TEXT DEFAULT '',
    content TEXT DEFAULT '',
    chapter_index INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    heat_score REAL DEFAULT 0.5,
    last_accessed_chapter INTEGER DEFAULT 0,
    access_count INTEGER DEFAULT 0,
    consolidated INTEGER DEFAULT 0
);

-- 卷册结构
CREATE TABLE IF NOT EXISTS volumes (
    volume_id TEXT PRIMARY KEY,
    novel_id TEXT NOT NULL,
    volume_index INTEGER NOT NULL,
    title TEXT DEFAULT '',
    description TEXT DEFAULT '',
    chapter_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (novel_id) REFERENCES novels(novel_id)
);

-- 卷册-章节映射
CREATE TABLE IF NOT EXISTS volume_chapters (
    novel_id TEXT NOT NULL,
    volume_id TEXT NOT NULL,
    chapter_index INTEGER NOT NULL,
    PRIMARY KEY (novel_id, chapter_index)
);

-- 伏笔
CREATE TABLE IF NOT EXISTS foreshadows (
    foreshadow_id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id TEXT NOT NULL,
    description TEXT DEFAULT '',
    chapter_index INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 检查点
CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    novel_id TEXT NOT NULL,
    chapter_index INTEGER DEFAULT 0,
    type TEXT DEFAULT '',
    state_json TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_scene_turns ON scene_turns(novel_id, chapter_index);
CREATE INDEX IF NOT EXISTS idx_character_actions ON character_actions(novel_id, chapter_index);
CREATE INDEX IF NOT EXISTS idx_episodic ON episodic_memories(novel_id, character_id);
