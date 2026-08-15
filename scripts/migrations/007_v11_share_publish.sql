-- Migration 007: V11 Share & Publish (Milestone 15)
-- Created: 2026-08-16
-- 需求 B: 公开分享 + 注册阅读；需求 A: 成书发布
-- 注意：这些表位于中央库（NOVEL_DB_PATH），与 invite_codes/user_quotas 同库

-- ── 分享链接（公开分享）──────────────────────────────
-- share id 为不可枚举随机短码(>=8位)
-- trial_mode: first_n_chapters | word_count | ratio
CREATE TABLE IF NOT EXISTS share_links (
    id TEXT PRIMARY KEY,
    novel_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    title_snapshot TEXT DEFAULT '',
    cover_snapshot TEXT DEFAULT '',
    intro_snapshot TEXT DEFAULT '',
    trial_mode TEXT DEFAULT 'first_n_chapters',
    trial_value INTEGER DEFAULT 3,
    status TEXT DEFAULT 'active',
    view_count INTEGER DEFAULT 0,
    read_count INTEGER DEFAULT 0,
    register_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    disabled_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_share_novel ON share_links(novel_id);
CREATE INDEX IF NOT EXISTS idx_share_owner ON share_links(owner_id);
CREATE INDEX IF NOT EXISTS idx_share_status ON share_links(status);

-- ── 分享每日流量统计（PV/阅读/UV）──────────────────
CREATE TABLE IF NOT EXISTS share_stats (
    share_id TEXT NOT NULL,
    stat_date TEXT NOT NULL,
    views INTEGER DEFAULT 0,
    reads INTEGER DEFAULT 0,
    visitors INTEGER DEFAULT 0,
    PRIMARY KEY (share_id, stat_date),
    FOREIGN KEY (share_id) REFERENCES share_links(id)
);

-- ── 试读→注册转化（去重）────────────────────────────
CREATE TABLE IF NOT EXISTS share_conversions (
    share_id TEXT NOT NULL,
    user_code TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (share_id, user_code),
    FOREIGN KEY (share_id) REFERENCES share_links(id)
);

-- ── 读者书架与阅读进度 ─────────────────────────────
CREATE TABLE IF NOT EXISTS read_progress (
    user_code TEXT NOT NULL,
    novel_id TEXT NOT NULL,
    share_id TEXT DEFAULT '',
    chapter_index INTEGER DEFAULT 0,
    in_bookshelf INTEGER DEFAULT 0,
    last_read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_code, novel_id)
);

CREATE INDEX IF NOT EXISTS idx_read_progress_user ON read_progress(user_code);

-- ── 发布记录（成书发布）─────────────────────────────
CREATE TABLE IF NOT EXISTS publication_records (
    id TEXT PRIMARY KEY,
    novel_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    stage TEXT DEFAULT 'draft',
    target_book_id TEXT DEFAULT '',
    target_url TEXT DEFAULT '',
    export_meta TEXT DEFAULT '{}',
    operator TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pub_novel ON publication_records(novel_id);
CREATE INDEX IF NOT EXISTS idx_pub_stage ON publication_records(stage);

-- ── 平台规范适配表 ─────────────────────────────────
CREATE TABLE IF NOT EXISTS platform_profiles (
    platform TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    formats TEXT DEFAULT 'txt',
    encoding TEXT DEFAULT 'utf-8',
    chapter_max_words INTEGER DEFAULT 0,
    supports_volumes INTEGER DEFAULT 0,
    cover_required INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1
);
