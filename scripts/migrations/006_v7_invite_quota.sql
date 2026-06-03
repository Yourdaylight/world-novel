-- Migration 006: V7 Invite Code & Quota System
-- Created: 2026-06-03
-- 邀请码用户系统 + Token额度管理 + 使用日志

-- 邀请码表
CREATE TABLE IF NOT EXISTS invite_codes (
    code TEXT PRIMARY KEY,
    description TEXT DEFAULT '',
    is_active BOOLEAN DEFAULT 1,
    created_by TEXT DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    used_count INTEGER DEFAULT 0,
    max_uses INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_invite_codes_active ON invite_codes(is_active);

-- 用户额度表
CREATE TABLE IF NOT EXISTS user_quotas (
    code TEXT PRIMARY KEY,
    total_tokens INTEGER DEFAULT 0,
    used_tokens INTEGER DEFAULT 0,
    total_requests INTEGER DEFAULT 0,
    used_requests INTEGER DEFAULT 0,
    chapter_quota INTEGER DEFAULT 0,
    chapters_used INTEGER DEFAULT 0,
    plan_type TEXT DEFAULT 'free',
    expires_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (code) REFERENCES invite_codes(code)
);

CREATE INDEX IF NOT EXISTS idx_user_quotas_plan ON user_quotas(plan_type);
CREATE INDEX IF NOT EXISTS idx_user_quotas_expires ON user_quotas(expires_at);

-- 用户Token使用日志
CREATE TABLE IF NOT EXISTS user_token_usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    role TEXT NOT NULL,
    chapter_index INTEGER DEFAULT -1,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    model TEXT DEFAULT '',
    description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_usage_code ON user_token_usage_log(code);
CREATE INDEX IF NOT EXISTS idx_user_usage_created ON user_token_usage_log(created_at);

-- 创建默认管理员邀请码（初始部署时使用）
-- 注意：部署后应立即修改默认密码
INSERT OR IGNORE INTO invite_codes (code, description, is_active, max_uses, created_by)
VALUES ('admin_default', 'Default admin invite code - CHANGE IMMEDIATELY', 1, 999999, 'system');

INSERT OR IGNORE INTO user_quotas (code, total_tokens, total_requests, chapter_quota, plan_type)
VALUES ('admin_default', 0, 0, 0, 'enterprise');
-- total_tokens=0 表示无限制（管理员账号）
