"""Auth dependency injection — mode-configurable (JWT or Casdoor Sidecar).

Active mode is driven by ``settings.auth_mode``:

- ``jwt`` (default, open-source) — invite-code login issues a JWT
  (python-jose, HS256); token-quota system gates generation.
- ``casdoor`` — browser auth proxied to casdoor-auth-sidecar
  (``POST /api/auth/verify``); session tokens verified via sidecar.
- ``disabled`` — all routes open (dev/staging).

``require_auth`` / ``optional_auth`` route strictly by mode — no cross-mode
fallback. Legacy ``NOVEL_AUTH_ENABLED=true`` env maps to ``casdoor`` mode.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from novel_creator.config import settings
from novel_creator.memory.database import get_connection
from novel_creator.memory.quota_store import check_and_deduct_tokens
from .sidecar_client import SidecarIdentity, get_sidecar

logger = logging.getLogger("novel_creator.web.auth")

# HTTP Bearer security scheme (for Authorization header)
security = HTTPBearer(auto_error=False)

# JWT 配置。优先读取 WORLDENGINE_JWT_SECRET（.env 经 config.load_dotenv 注入），
# 其次 NOVEL_JWT_SECRET（settings.jwt_secret），最后才是开发默认值。
_JWT_SECRET = (
    os.environ.get("WORLDENGINE_JWT_SECRET")
    or settings.jwt_secret
    or "worldengine-dev-secret-change-in-production"
)
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_HOURS = 168  # 7天


def is_admin_code(code: str) -> bool:
    """Whether an invite code grants admin (configurable prefix, default 'admin')."""
    return bool(code) and code.startswith(settings.admin_code_prefix or "admin")


@dataclass
class AuthUser:
    """Authenticated user info.

    JWT users carry ``code`` (invite code) and ``is_admin``.
    Sidecar users carry sub/username/display_name/email/organization/token.
    """

    sub: str = ""            # Casdoor user ID (e.g., "JQ/username")
    username: str = ""
    display_name: str = ""
    email: str = ""
    organization: str = ""
    token: str = ""          # sidecar session token / raw bearer
    code: str = ""           # JWT user invite code
    is_admin: bool = False

    @classmethod
    def from_identity(cls, identity: SidecarIdentity, token: str) -> "AuthUser":
        return cls(
            sub=identity.sub,
            username=identity.username,
            display_name=identity.display_name,
            email=identity.email,
            organization=identity.organization,
            token=token,
            is_admin=_is_admin(identity),
        )

    @classmethod
    def from_jwt(cls, code: str, is_admin: bool) -> "AuthUser":
        return cls(code=code, is_admin=is_admin, username=code, sub=code)


class QuotaCheckError(HTTPException):
    """额度不足异常。"""

    def __init__(self, detail: str = "Quota exceeded"):
        super().__init__(status_code=402, detail=detail)


def _is_admin(identity: SidecarIdentity) -> bool:
    """Admin detection: sub contains 'admin' or org is 'JQ' and username starts with 'admin'."""
    sub_lower = identity.sub.lower()
    username_lower = identity.username.lower()
    return (
        "admin" in sub_lower
        or username_lower.startswith("admin")
    )


def _extract_token(request: Request) -> str:
    """Extract auth token from request.

    Priority: X-User-Token header > Authorization: Bearer *** > query ?token
    """
    # 1. X-User-Token header (preferred)
    token = request.headers.get("X-User-Token", "").strip()
    if token:
        return token

    # 2. Authorization: Bearer ***
    auth = request.headers.get("Authorization", "").strip()
    if auth.startswith("Bearer "):
        return auth[7:].strip()

    # 3. Query parameter (for WebSocket / legacy)
    token = request.query_params.get("token", "").strip()
    return token


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
        # 双重校验：管理员前缀的 code 强制设为管理员
        if is_admin_code(code):
            is_admin = True

        return AuthUser.from_jwt(code=code, is_admin=is_admin)

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def _verify_sidecar(token: str) -> AuthUser | None:
    """Verify a Casdoor sidecar session token. Returns AuthUser or None."""
    sidecar = get_sidecar()
    result = await sidecar.verify(token)

    if not result.ok or result.identity is None:
        return None

    user = AuthUser.from_identity(result.identity, token)
    # Update token in case sidecar issued a new one during refresh
    if result.token and result.token != token:
        user.token = result.token

    logger.debug("auth: user=%s sub=%s", user.username, user.sub)
    return user


async def require_auth(request: Request) -> AuthUser:
    """FastAPI dependency: require valid auth for the active auth_mode.

    Mode routing:
      - ``disabled`` — returns anonymous user (dev/staging)
      - ``casdoor``  — requires a valid Casdoor sidecar session token
      - ``jwt``      — requires a valid JWT (invite-code / token-quota system)

    Raises HTTPException(401) if no valid token is found.

    Usage:
        @router.get("/protected")
        async def protected_endpoint(user: AuthUser = Depends(require_auth)):
            ...
    """
    if settings.auth_mode == "disabled":
        # Auth disabled — return anonymous user (useful for dev/staging)
        return AuthUser(sub="anonymous", username="anonymous", token="")

    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if settings.auth_mode == "casdoor":
        user = await _verify_sidecar(token)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="登录已过期，请重新登录",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    # Default: jwt mode — strict JWT verification, no fallback
    return verify_token(token)


async def require_admin(user: AuthUser = Depends(require_auth)) -> AuthUser:
    """FastAPI dependency: require admin user.

    Usage:
        @router.get("/admin/endpoint")
        async def admin_endpoint(user: AuthUser = Depends(require_admin)):
            ...
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user


async def optional_auth(request: Request) -> AuthUser | None:
    """FastAPI dependency: optionally authenticate user for the active auth_mode.

    Returns AuthUser if token is valid (per mode), None otherwise.
    Never raises 401.

    Usage:
        @router.get("/optional")
        async def optional_endpoint(user: Optional[AuthUser] = Depends(optional_auth)):
            if user:
                ...
    """
    if settings.auth_mode == "disabled":
        return AuthUser(sub="anonymous", username="anonymous", token="")

    token = _extract_token(request)
    if not token:
        return None

    if settings.auth_mode == "casdoor":
        return await _verify_sidecar(token)

    # Default: jwt mode — strict JWT verification, no fallback
    try:
        return verify_token(token)
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
    if is_admin_code(code):
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
        logger.warning("Quota check failed for %s: %s", code, e)
