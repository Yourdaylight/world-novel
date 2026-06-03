"""认证路由 - 邀请码登录、额度查询。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from novel_creator.config import settings
from novel_creator.memory.database import get_connection
from novel_creator.memory.quota_store import (
    validate_invite_code,
    increment_code_usage,
    get_user_quota,
    ensure_user_quota_exists,
)
from novel_creator.web.auth_deps import (
    create_access_token,
    require_auth,
    AuthUser,
)

router = APIRouter()


class LoginRequest(BaseModel):
    """登录请求模型。"""
    invite_code: str


class LoginResponse(BaseModel):
    """登录响应模型。"""
    access_token: str
    token_type: str
    code: str
    quota: dict


class QuotaResponse(BaseModel):
    """额度响应模型。"""
    code: str
    total_tokens: int
    used_tokens: int
    remaining_tokens: int
    total_requests: int
    used_requests: int
    remaining_requests: int
    chapter_quota: int
    chapters_used: int
    remaining_chapters: int
    plan_type: str
    expires_at: Optional[str]


@router.post("/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """邀请码登录 - 验证邀请码，返回JWT和额度信息。

    流程：
    1. 验证邀请码是否有效
    2. 确保用户配额记录存在（首次登录创建默认配额）
    3. 增加邀请码使用计数
    4. 生成JWT访问令牌
    5. 返回token和额度信息

    Args:
        req: 登录请求，包含邀请码

    Returns:
        包含access_token、token类型、用户code和额度信息的响应

    Raises:
        HTTPException: 401 如果邀请码无效
    """
    code = req.invite_code.strip()

    # 1. 验证邀请码
    conn = await get_connection(settings.db_path)
    try:
        is_valid = await validate_invite_code(conn, code)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid invite code",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 2. 确保用户配额记录存在（首次登录创建）
        await ensure_user_quota_exists(conn, code)

        # 3. 增加邀请码使用计数
        await increment_code_usage(conn, code)

        # 4. 获取用户额度信息
        quota = await get_user_quota(conn, code)
    finally:
        await conn.close()

    # 5. 生成JWT
    is_admin = code.startswith("admin")
    access_token = create_access_token(code=code, is_admin=is_admin)

    # 6. 返回响应
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        code=code,
        quota=quota,
    )


@router.get("/auth/quota", response_model=QuotaResponse)
async def get_my_quota(auth: AuthUser = Depends(require_auth)):
    """获取当前登录用户的额度信息。

    需要有效的JWT认证。返回用户的token额度、请求次数额度、章节额度等。

    Args:
        auth: 已认证的用户信息

    Returns:
        用户额度详细信息
    """
    conn = await get_connection(settings.db_path)
    try:
        quota = await get_user_quota(conn, auth.code)
    finally:
        await conn.close()

    # 计算剩余额度
    total_tokens = quota.get("total_tokens", 0)
    used_tokens = quota.get("used_tokens", 0)
    total_requests = quota.get("total_requests", 0)
    used_requests = quota.get("used_requests", 0)
    chapter_quota = quota.get("chapter_quota", 0)
    chapters_used = quota.get("chapters_used", 0)

    return QuotaResponse(
        code=quota["code"],
        total_tokens=total_tokens,
        used_tokens=used_tokens,
        remaining_tokens=max(0, total_tokens - used_tokens) if total_tokens > 0 else -1,
        total_requests=total_requests,
        used_requests=used_requests,
        remaining_requests=max(0, total_requests - used_requests) if total_requests > 0 else -1,
        chapter_quota=chapter_quota,
        chapters_used=chapters_used,
        remaining_chapters=max(0, chapter_quota - chapters_used) if chapter_quota > 0 else -1,
        plan_type=quota.get("plan_type", "free"),
        expires_at=quota.get("expires_at"),
    )


@router.post("/auth/refresh")
async def refresh_token(auth: AuthUser = Depends(require_auth)):
    """刷新JWT令牌。

    用当前已认证用户的信息重新生成一个新的JWT令牌。
    用于token即将过期时获取新token。

    Args:
        auth: 已认证的用户信息

    Returns:
        包含新的access_token的响应
    """
    # 重新生成token，保持相同的用户信息和admin状态
    new_token = create_access_token(code=auth.code, is_admin=auth.is_admin)

    return {
        "access_token": new_token,
        "token_type": "bearer",
        "code": auth.code,
        "is_admin": auth.is_admin,
    }
