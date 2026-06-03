"""用户配额管理模块 - 提供邀请码和Token额度的CRUD操作。"""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone
from typing import Optional

import aiosqlite


# ========== 邀请码管理 ==========


async def create_invite_code(
    conn: aiosqlite.Connection,
    code: Optional[str] = None,
    description: str = "",
    max_uses: int = 1,
    created_by: str = "admin",
) -> str:
    """创建新的邀请码。如果未提供code，自动生成8位随机码。"""
    if code is None:
        # 生成8位随机邀请码（大小写字母+数字），排除易混淆字符
        alphabet = string.ascii_letters + string.digits
        alphabet = alphabet.replace("O", "").replace("0", "").replace("I", "").replace("l", "")
        code = "".join(secrets.choice(alphabet) for _ in range(8))

    now = datetime.now(timezone.utc).isoformat()
    await conn.execute(
        """
        INSERT INTO invite_codes (code, description, max_uses, created_by, created_at, is_active, used_count)
        VALUES (?, ?, ?, ?, ?, 1, 0)
        """,
        (code, description, max_uses, created_by, now),
    )
    await conn.commit()
    return code


async def get_invite_code(conn: aiosqlite.Connection, code: str) -> Optional[dict]:
    """查询邀请码详情，包括配额信息。"""
    async with conn.execute(
        """
        SELECT
            ic.code, ic.description, ic.is_active, ic.created_by,
            ic.created_at, ic.used_count, ic.max_uses,
            uq.total_tokens, uq.used_tokens, uq.total_requests, uq.used_requests,
            uq.chapter_quota, uq.chapters_used, uq.plan_type, uq.expires_at
        FROM invite_codes ic
        LEFT JOIN user_quotas uq ON ic.code = uq.code
        WHERE ic.code = ?
        """,
        (code,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def list_invite_codes(conn: aiosqlite.Connection) -> list[dict]:
    """列出所有邀请码及其配额概览。"""
    async with conn.execute(
        """
        SELECT
            ic.code, ic.description, ic.is_active, ic.created_by,
            ic.created_at, ic.used_count, ic.max_uses,
            COALESCE(uq.total_tokens, 0) as total_tokens,
            COALESCE(uq.used_tokens, 0) as used_tokens,
            COALESCE(uq.total_requests, 0) as total_requests,
            COALESCE(uq.used_requests, 0) as used_requests,
            COALESCE(uq.chapter_quota, 0) as chapter_quota,
            COALESCE(uq.chapters_used, 0) as chapters_used,
            COALESCE(uq.plan_type, 'free') as plan_type,
            uq.expires_at
        FROM invite_codes ic
        LEFT JOIN user_quotas uq ON ic.code = uq.code
        ORDER BY ic.created_at DESC
        """
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def validate_invite_code(conn: aiosqlite.Connection, code: str) -> bool:
    """验证邀请码是否有效（存在、激活、未超使用次数）。"""
    async with conn.execute(
        """
        SELECT is_active, used_count, max_uses
        FROM invite_codes
        WHERE code = ?
        """,
        (code,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return False
        # max_uses = 0 表示无限制使用次数
        is_active, used_count, max_uses = row["is_active"], row["used_count"], row["max_uses"]
        if not is_active:
            return False
        if max_uses > 0 and used_count >= max_uses:
            return False
        return True


async def increment_code_usage(conn: aiosqlite.Connection, code: str) -> None:
    """增加邀请码使用计数。"""
    await conn.execute(
        """
        UPDATE invite_codes
        SET used_count = used_count + 1
        WHERE code = ?
        """,
        (code,),
    )
    await conn.commit()


async def deactivate_invite_code(conn: aiosqlite.Connection, code: str) -> bool:
    """禁用邀请码。"""
    await conn.execute(
        """
        UPDATE invite_codes
        SET is_active = 0
        WHERE code = ?
        """,
        (code,),
    )
    await conn.commit()
    # 返回是否实际更新了记录
    async with conn.execute(
        "SELECT changes() as affected"
    ) as cursor:
        row = await cursor.fetchone()
        return row["affected"] > 0


async def delete_invite_code(conn: aiosqlite.Connection, code: str) -> bool:
    """删除邀请码及其配额记录。"""
    # 先删除关联的配额记录（外键约束，但 SQLite 默认不强制，手动清理更保险）
    await conn.execute(
        "DELETE FROM user_quotas WHERE code = ?",
        (code,),
    )
    # 删除关联的使用日志
    await conn.execute(
        "DELETE FROM user_token_usage_log WHERE code = ?",
        (code,),
    )
    # 删除邀请码本身
    await conn.execute(
        "DELETE FROM invite_codes WHERE code = ?",
        (code,),
    )
    await conn.commit()
    async with conn.execute(
        "SELECT changes() as affected"
    ) as cursor:
        row = await cursor.fetchone()
        return row["affected"] > 0


# ========== 配额管理 ==========


async def get_user_quota(conn: aiosqlite.Connection, code: str) -> Optional[dict]:
    """获取用户配额详情。"""
    async with conn.execute(
        """
        SELECT
            code, total_tokens, used_tokens, total_requests, used_requests,
            chapter_quota, chapters_used, plan_type, expires_at,
            updated_at, created_at
        FROM user_quotas
        WHERE code = ?
        """,
        (code,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def set_user_quota(
    conn: aiosqlite.Connection,
    code: str,
    total_tokens: Optional[int] = None,
    total_requests: Optional[int] = None,
    chapter_quota: Optional[int] = None,
    plan_type: Optional[str] = None,
    expires_at: Optional[str] = None,
) -> None:
    """设置（覆盖）用户配额。Admin用。"""
    now = datetime.now(timezone.utc).isoformat()

    # 先确保配额记录存在
    await ensure_user_quota_exists(conn, code)

    # 构建动态更新字段
    fields = ["updated_at = ?"]
    params: list = [now]

    if total_tokens is not None:
        fields.append("total_tokens = ?")
        params.append(total_tokens)
    if total_requests is not None:
        fields.append("total_requests = ?")
        params.append(total_requests)
    if chapter_quota is not None:
        fields.append("chapter_quota = ?")
        params.append(chapter_quota)
    if plan_type is not None:
        fields.append("plan_type = ?")
        params.append(plan_type)
    if expires_at is not None:
        fields.append("expires_at = ?")
        params.append(expires_at)

    params.append(code)
    sql = f"UPDATE user_quotas SET {', '.join(fields)} WHERE code = ?"

    await conn.execute(sql, params)
    await conn.commit()


async def add_user_quota(
    conn: aiosqlite.Connection,
    code: str,
    tokens: int = 0,
    requests: int = 0,
    chapters: int = 0,
) -> None:
    """增加用户配额（充值）。Admin用。"""
    now = datetime.now(timezone.utc).isoformat()

    # 先确保配额记录存在
    await ensure_user_quota_exists(conn, code)

    await conn.execute(
        """
        UPDATE user_quotas
        SET total_tokens = total_tokens + ?,
            total_requests = total_requests + ?,
            chapter_quota = chapter_quota + ?,
            updated_at = ?
        WHERE code = ?
        """,
        (tokens, requests, chapters, now, code),
    )
    await conn.commit()


async def check_and_deduct_tokens(
    conn: aiosqlite.Connection,
    code: str,
    tokens_needed: int = 0,
    requests_needed: int = 1,
) -> tuple[bool, Optional[str]]:
    """检查并扣减Token/请求额度。

    返回: (是否允许, 错误信息)
    如果total_tokens=0且total_requests=0视为无限制（管理员账号）。
    """
    # 先确保配额记录存在
    await ensure_user_quota_exists(conn, code)

    async with conn.execute(
        """
        SELECT total_tokens, used_tokens, total_requests, used_requests, chapter_quota, chapters_used
        FROM user_quotas
        WHERE code = ?
        """,
        (code,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return False, "用户配额记录不存在"

        total_tokens = row["total_tokens"]
        used_tokens = row["used_tokens"]
        total_requests = row["total_requests"]
        used_requests = row["used_requests"]

    # 管理员账号：total_tokens=0 且 total_requests=0 视为无限制
    if total_tokens == 0 and total_requests == 0:
        # 仍然需要记录使用量，但不阻止操作
        now = datetime.now(timezone.utc).isoformat()
        await conn.execute(
            """
            UPDATE user_quotas
            SET used_tokens = used_tokens + ?,
                used_requests = used_requests + ?,
                updated_at = ?
            WHERE code = ?
            """,
            (tokens_needed, requests_needed, now, code),
        )
        await conn.commit()
        return True, None

    # 检查Token额度
    if total_tokens > 0:
        if used_tokens + tokens_needed > total_tokens:
            return False, f"Token额度不足: 已用 {used_tokens}/{total_tokens}, 需要 {tokens_needed}"

    # 检查请求额度
    if total_requests > 0:
        if used_requests + requests_needed > total_requests:
            return False, f"请求额度不足: 已用 {used_requests}/{total_requests}, 需要 {requests_needed}"

    # 扣减额度
    now = datetime.now(timezone.utc).isoformat()
    await conn.execute(
        """
        UPDATE user_quotas
        SET used_tokens = used_tokens + ?,
            used_requests = used_requests + ?,
            updated_at = ?
        WHERE code = ?
        """,
        (tokens_needed, requests_needed, now, code),
    )
    await conn.commit()
    return True, None


async def deduct_chapter_quota(conn: aiosqlite.Connection, code: str) -> bool:
    """扣减章节配额。返回是否成功。"""
    await ensure_user_quota_exists(conn, code)

    async with conn.execute(
        """
        SELECT chapter_quota, chapters_used
        FROM user_quotas
        WHERE code = ?
        """,
        (code,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return False
        chapter_quota, chapters_used = row["chapter_quota"], row["chapters_used"]

    # chapter_quota = 0 视为无限制
    if chapter_quota > 0 and chapters_used >= chapter_quota:
        return False

    now = datetime.now(timezone.utc).isoformat()
    await conn.execute(
        """
        UPDATE user_quotas
        SET chapters_used = chapters_used + 1,
            updated_at = ?
        WHERE code = ?
        """,
        (now, code),
    )
    await conn.commit()
    return True


# ========== 使用日志 ==========


async def log_user_token_usage(
    conn: aiosqlite.Connection,
    code: str,
    role: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    model: str = "",
    chapter_index: int = -1,
    description: str = "",
) -> None:
    """记录用户的Token使用日志，同时更新user_quotas的used_tokens/used_requests。"""
    now = datetime.now(timezone.utc).isoformat()

    # 插入使用日志
    await conn.execute(
        """
        INSERT INTO user_token_usage_log
        (code, role, chapter_index, prompt_tokens, completion_tokens, total_tokens, model, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (code, role, chapter_index, prompt_tokens, completion_tokens, total_tokens, model, description, now),
    )

    # 同时更新 user_quotas 的 used_tokens 和 used_requests
    await conn.execute(
        """
        UPDATE user_quotas
        SET used_tokens = used_tokens + ?,
            used_requests = used_requests + 1,
            updated_at = ?
        WHERE code = ?
        """,
        (total_tokens, now, code),
    )

    await conn.commit()


async def get_user_usage_logs(
    conn: aiosqlite.Connection,
    code: str,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """获取用户Token使用日志。"""
    async with conn.execute(
        """
        SELECT
            id, code, role, chapter_index, prompt_tokens, completion_tokens,
            total_tokens, model, description, created_at
        FROM user_token_usage_log
        WHERE code = ?
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        (code, limit, offset),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_usage_summary(conn: aiosqlite.Connection, code: Optional[str] = None) -> dict:
    """获取使用统计摘要（全局或单个用户）。"""
    summary: dict = {}

    if code:
        # 单个用户的统计
        async with conn.execute(
            """
            SELECT
                COALESCE(SUM(total_tokens), 0) as total_tokens_used,
                COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                COUNT(*) as total_requests
            FROM user_token_usage_log
            WHERE code = ?
            """,
            (code,),
        ) as cursor:
            row = await cursor.fetchone()
            summary["usage_stats"] = dict(row) if row else {
                "total_tokens_used": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_requests": 0,
            }

        # 获取按角色分组的统计
        async with conn.execute(
            """
            SELECT
                role,
                COALESCE(SUM(total_tokens), 0) as tokens_used,
                COUNT(*) as request_count
            FROM user_token_usage_log
            WHERE code = ?
            GROUP BY role
            """,
            (code,),
        ) as cursor:
            rows = await cursor.fetchall()
            summary["by_role"] = [dict(row) for row in rows]

        # 获取当前配额状态
        quota = await get_user_quota(conn, code)
        summary["quota"] = quota
    else:
        # 全局统计
        async with conn.execute(
            """
            SELECT
                COALESCE(SUM(total_tokens), 0) as total_tokens_used,
                COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                COUNT(*) as total_requests
            FROM user_token_usage_log
            """
        ) as cursor:
            row = await cursor.fetchone()
            summary["usage_stats"] = dict(row) if row else {
                "total_tokens_used": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_requests": 0,
            }

        # 获取用户数统计
        async with conn.execute(
            """
            SELECT COUNT(DISTINCT code) as user_count FROM user_token_usage_log
            """
        ) as cursor:
            row = await cursor.fetchone()
            summary["active_users"] = row["user_count"] if row else 0

        # 按角色全局统计
        async with conn.execute(
            """
            SELECT
                role,
                COALESCE(SUM(total_tokens), 0) as tokens_used,
                COUNT(*) as request_count
            FROM user_token_usage_log
            GROUP BY role
            """
        ) as cursor:
            rows = await cursor.fetchall()
            summary["by_role"] = [dict(row) for row in rows]

        # 邀请码总数统计
        async with conn.execute(
            """
            SELECT
                COUNT(*) as total_codes,
                SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_codes
            FROM invite_codes
            """
        ) as cursor:
            row = await cursor.fetchone()
            summary["invite_codes"] = dict(row) if row else {"total_codes": 0, "active_codes": 0}

    return summary


# ========== 辅助函数 ==========


async def ensure_user_quota_exists(conn: aiosqlite.Connection, code: str) -> None:
    """确保用户配额记录存在，不存在则创建默认记录。"""
    async with conn.execute(
        "SELECT 1 FROM user_quotas WHERE code = ?",
        (code,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is not None:
            return  # 已存在，无需创建

    now = datetime.now(timezone.utc).isoformat()
    # 插入默认配额记录
    await conn.execute(
        """
        INSERT OR IGNORE INTO user_quotas
        (code, total_tokens, used_tokens, total_requests, used_requests,
         chapter_quota, chapters_used, plan_type, created_at, updated_at)
        VALUES (?, 0, 0, 0, 0, 0, 0, 'free', ?, ?)
        """,
        (code, now, now),
    )
    await conn.commit()


async def get_db_connection() -> aiosqlite.Connection:
    """获取数据库连接（从database导入）。"""
    from novel_creator.memory.database import get_connection

    return await get_connection()
