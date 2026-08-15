"""Auth routes — unified: JWT (invite-code/quota) + Casdoor Sidecar.

Remote (06e3934) routes:
  POST /auth/login        — invite-code login, returns JWT + quota
  GET  /auth/quota        — current user quota (JWT)
  POST /auth/refresh      — refresh JWT

Local (Casdoor sidecar) routes:
  GET  /auth/config                       — auth mode config for frontend
  GET/POST /auth/sidecar/login            — proxy to sidecar login
  GET  /auth/sidecar/callback             — Casdoor OAuth callback
  POST /auth/sidecar/logout               — destroy sidecar session
  GET  /auth/sidecar/logout-complete      — post-Casdoor-logout bridge
  GET  /auth/me                           — current user info
  POST /auth/sidecar/refresh              — refresh sidecar session token
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response, JSONResponse
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
from ..sidecar_client import get_sidecar

router = APIRouter()


# ══════════════════════════════════════════════════════════════
# JWT / invite-code login (remote 06e3934)
# ══════════════════════════════════════════════════════════════

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
    """邀请码登录 - 验证邀请码，返回JWT和额度信息。"""
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
    """获取当前登录用户的额度信息。"""
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
    """刷新JWT令牌。"""
    new_token = create_access_token(code=auth.code, is_admin=auth.is_admin)

    return {
        "access_token": new_token,
        "token_type": "bearer",
        "code": auth.code,
        "is_admin": auth.is_admin,
    }


# ══════════════════════════════════════════════════════════════
# Casdoor Sidecar auth (local line)
# ══════════════════════════════════════════════════════════════

@router.get("/auth/config")
async def auth_config():
    """Return auth configuration for the frontend.

    Frontend reads this to determine the active auth mode and
    which URLs to use for login/logout.
    """
    mode = settings.auth_mode

    if mode == "casdoor":
        sidecar = get_sidecar()
        app_cfg = await sidecar.get_app_config() if sidecar.enabled else None
        return {
            "mode": "casdoor",
            "sidecar_enabled": True,
            "login_url": "/api/auth/sidecar/login",
            "oauth_login_url": "/api/auth/sidecar/login?mode=redirect",
            "logout_url": "/api/auth/sidecar/logout",
            "organization": (app_cfg or {}).get("organization", ""),
            "application": (app_cfg or {}).get("application", ""),
        }
    elif mode == "jwt":
        return {
            "mode": "jwt",
            "sidecar_enabled": False,
            "login_url": "/api/auth/login",
            "logout_url": None,
        }
    else:
        return {
            "mode": "disabled",
            "sidecar_enabled": False,
        }


async def _proxy_get_to_sidecar(request: Request, sidecar_path: str):
    """Proxy a GET request to sidecar, forwarding query params and response as-is."""
    sidecar = get_sidecar()
    if not sidecar.enabled:
        return JSONResponse({"error": "auth not configured"}, status_code=503)

    params: dict[str, str] = {}
    for key, value in request.query_params.multi_items():
        params[key] = value

    try:
        resp = await sidecar.proxy_get(sidecar_path, params=params or None)
        if resp is None:
            return JSONResponse({"error": "sidecar unreachable"}, status_code=502)
    except Exception as e:
        return JSONResponse({"error": f"sidecar unreachable: {e}"}, status_code=502)

    if resp.status_code in (301, 302, 303, 307, 308):
        location = resp.headers.get("Location", "")
        if location:
            return RedirectResponse(url=location, status_code=resp.status_code)

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers={k: v for k, v in resp.headers.items() if k.lower() not in ("transfer-encoding", "content-encoding")},
        media_type=resp.headers.get("content-type"),
    )


@router.get("/auth/sidecar/login")
async def sidecar_login_get(request: Request):
    """Proxy login to sidecar (GET → OAuth redirect or HTML login page)."""
    return await _proxy_get_to_sidecar(request, "/api/auth/login")


@router.post("/auth/sidecar/login")
async def sidecar_login_post(request: Request):
    """Proxy JSON password login to sidecar's password-login endpoint."""
    sidecar = get_sidecar()
    if not sidecar.enabled:
        return JSONResponse({"error": "auth not configured"}, status_code=503)

    try:
        body = await request.body()
        resp = await sidecar.proxy_post("/api/auth/password-login", content=body)
        if resp is None:
            return JSONResponse({"error": "sidecar unreachable"}, status_code=502)

        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location", "")
            if location:
                return RedirectResponse(url=location, status_code=resp.status_code)

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers={k: v for k, v in resp.headers.items() if k.lower() not in ("transfer-encoding", "content-encoding")},
            media_type=resp.headers.get("content-type"),
        )
    except Exception as e:
        return JSONResponse({"error": f"sidecar unreachable: {e}"}, status_code=502)


@router.get("/auth/sidecar/callback")
async def sidecar_callback(request: Request):
    """Proxy Casdoor OAuth callback to sidecar."""
    sidecar = get_sidecar()
    if not sidecar.enabled:
        return JSONResponse({"error": "auth not configured"}, status_code=503)

    params: dict[str, str] = {}
    for key, value in request.query_params.multi_items():
        params[key] = value

    try:
        resp = await sidecar.proxy_get("/api/auth/callback", params=params or None)
        if resp is None:
            return JSONResponse({"error": "sidecar unreachable"}, status_code=502)
    except Exception as e:
        return JSONResponse({"error": f"sidecar unreachable: {e}"}, status_code=502)

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers={k: v for k, v in resp.headers.items() if k.lower() not in ("transfer-encoding", "content-encoding")},
        media_type=resp.headers.get("content-type"),
    )


@router.post("/auth/sidecar/logout")
async def sidecar_logout(request: Request):
    """Proxy logout to sidecar — destroy sidecar session."""
    sidecar = get_sidecar()
    if not sidecar.enabled:
        return {"ok": True}

    token = request.headers.get("X-User-Token", "").strip()
    if not token:
        auth = request.headers.get("Authorization", "").strip()
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
    if not token:
        try:
            body = await request.json()
            if isinstance(body, dict):
                token = body.get("token", "")
        except Exception:
            pass

    if token:
        await sidecar.logout(token)

    return {"ok": True}


@router.get("/auth/sidecar/logout-complete")
async def sidecar_logout_complete(request: Request):
    """Proxy logout-complete to sidecar (post-Casdoor-logout bridge page)."""
    return await _proxy_get_to_sidecar(request, "/api/auth/logout-complete")


@router.get("/auth/me")
async def auth_me(user: AuthUser = Depends(require_auth)):
    """Return current user info and token."""
    return {
        "ok": True,
        "user": {
            "sub": user.sub,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "organization": user.organization,
            "code": user.code,
            "is_admin": user.is_admin,
        },
        "token": user.token,
    }


@router.post("/auth/sidecar/refresh")
async def auth_sidecar_refresh(request: Request):
    """Refresh sidecar session token (renamed from /auth/refresh to avoid
    clashing with the JWT refresh route)."""
    token = request.headers.get("X-User-Token", "").strip()
    if not token:
        auth = request.headers.get("Authorization", "").strip()
        if auth.startswith("Bearer "):
            token = auth[7:].strip()

    if not token:
        raise HTTPException(status_code=401, detail="请先登录")

    sidecar = get_sidecar()
    result = await sidecar.refresh(token)

    if not result.ok:
        raise HTTPException(status_code=401, detail=result.error or "续期失败")

    return {
        "ok": True,
        "token": result.token,
    }
