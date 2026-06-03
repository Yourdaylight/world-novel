"""认证依赖模块 - 提供JWT认证和权限控制。"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from pydantic import BaseModel

from novel_creator.config import settings
from novel_creator.memory.database import get_connection
from novel_creator.memory.quota_store import check_and_deduct_tokens

# JWT配置
_JWT_SECRET = os.environ.get("NOVEL_JWT_SECRET", "worldengine-dev-secret-change-in-production")
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_HOURS = 168  # 7天

# 安全中间件
security = HTTPBearer(auto_error=False)


class AuthUser(BaseModel):
    """认证用户信息。"""
    code: str
    is_admin: bool = False


class QuotaCheckError(HTTPException):
    """额度不足异常。"""
    def __init__(self, detail: str = "Quota exceeded"):
        super().__init__(status_code=402, detail=detail)


def create_access_token(code: str, is_admin: bool = False) -> str:
    """创建JWT访问令牌。

    Token payload包含:
        - code: 用户邀请码
        - is_admin: 是否为管理员
        - exp: 过期时间
        - iat: 签发时间

    Args:
        code: 用户邀请码
        is_admin: 是否为管理员

    Returns:
        JWT编码的访问令牌字符串
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=_JWT_EXPIRE_HOURS)

    payload = {
        "code": code,
        "is_admin": is_admin,
        "exp": expire,
        "iat": now,
    }

    token = jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)
    return token


def verify_token(token: str) -> AuthUser:
    """验证JWT令牌，返回认证用户信息。

    Args:
        token: JWT令牌字符串

    Returns:
        AuthUser对象

    Raises:
        HTTPException: 401 如果token无效或过期
    """
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])

        code = payload.get("code")
        if code is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing code",
                headers={"WWW-Authenticate": "Bearer"},
            )

        is_admin = payload.get("is_admin", False)
        # 双重校验：code以"admin"开头的强制设为管理员
        if code.startswith("admin"):
            is_admin = True

        return AuthUser(code=code, is_admin=is_admin)

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> AuthUser:
    """认证依赖 - 需要有效JWT。

    用于保护需要登录的API端点。如果请求中没有提供有效的Bearer token，
    将返回401 Unauthorized。

    Args:
        credentials: HTTP Bearer认证凭据

    Returns:
        AuthUser对象

    Raises:
        HTTPException: 401 如果没有提供凭据或token无效
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return verify_token(credentials.credentials)


async def require_admin(auth: AuthUser = Depends(require_auth)) -> AuthUser:
    """管理员权限依赖 - 需要admin标识。

    在require_auth基础上进一步检查用户是否为管理员。
    目前判断规则：code以"admin"开头的为管理员。

    Args:
        auth: 已认证的用户信息

    Returns:
        AuthUser对象（管理员）

    Raises:
        HTTPException: 403 如果用户不是管理员
    """
    if not auth.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return auth


async def optional_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[AuthUser]:
    """可选认证 - 有token则验证，没有则返回None。

    用于那些既支持匿名访问又支持认证访问的端点。
    如果提供了token则验证并返回用户信息，否则返回None。

    Args:
        request: FastAPI请求对象
        credentials: HTTP Bearer认证凭据（可选）

    Returns:
        AuthUser对象或None
    """
    if credentials is None:
        return None

    try:
        return verify_token(credentials.credentials)
    except HTTPException:
        return None


async def check_quota_before_generation(code: str) -> None:
    """在生成前检查用户额度。

    连接到数据库，调用quota_store.check_and_deduct_tokens检查额度。
    额度不足时抛出QuotaCheckError(402)。

    Args:
        code: 用户邀请码

    Raises:
        QuotaCheckError: 402 如果额度不足
    """
    # 管理员不限额度
    if code.startswith("admin"):
        return

    try:
        conn = await get_connection(settings.db_path)
        try:
            # 检查并扣除1次请求额度（生成操作至少消耗1次请求）
            ok, err_msg = await check_and_deduct_tokens(
                conn, code, tokens_needed=0, requests_needed=1
            )
            if not ok:
                raise QuotaCheckError(
                    detail=f"Quota exceeded: {err_msg}"
                )
        finally:
            await conn.close()
    except QuotaCheckError:
        raise
    except Exception as e:
        # 数据库连接异常时记录日志，但允许继续（降级处理）
        # 生产环境建议改为拒绝
        import logging
        logging.getLogger("novel_creator.web.auth").warning(
            "Quota check failed for %s: %s", code, e
        )
