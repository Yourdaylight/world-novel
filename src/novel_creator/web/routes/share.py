"""Share routes — 公开分享 + 注册阅读（需求 B）。

公开面（无需登录，限流）：
  GET  /share/{id}            分享页元数据
  GET  /share/{id}/chapters   目录（仅标题 + 是否可读标记，绝不含正文）
  GET  /share/{id}/chapter/{n} 章节正文（匿名=试读边界，注册=全文）

作者面（require_auth）：
  POST /share                 创建/获取分享
  GET  /share/mine            我的分享列表
  PATCH /share/{id}           改试读策略 / 关闭（owner only）

读者面（require_auth）：
  GET  /bookshelf             书架 + 进度
  POST /bookshelf/progress    显式上报进度
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from novel_creator.config import settings
from novel_creator.memory.database import get_connection
from novel_creator.publishing.loader import load_novel_content
from novel_creator.sharing import store
from novel_creator.sharing.policy import is_chapter_readable, trial_chapter_count
from novel_creator.sharing.ratelimit import is_trusted_proxy, share_rate_limiter

from ..auth_deps import AuthUser, optional_auth, require_auth

public_router = APIRouter()
router = APIRouter(dependencies=[Depends(require_auth)])

VALID_TRIAL_MODES = {"first_n_chapters", "word_count", "ratio"}


def _client_ip(request: Request) -> str:
    """真实客户端 IP。

    仅当直连方是受信代理（loopback/内网，即 nginx 反代）时才采信
    X-Real-IP / X-Forwarded-For；XFF 取最右一跳（nginx $proxy_add_x_forwarded_for
    把真实客户端追加在最右），防止攻击者用伪造 XFF 绕过限流。
    """
    direct = request.client.host if request.client else "unknown"
    if not is_trusted_proxy(direct):
        return direct
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    forwarded = request.headers.get("x-forwarded-for", "")
    parts = [p.strip() for p in forwarded.split(",") if p.strip()]
    return parts[-1] if parts else direct


def _is_authenticated(user: AuthUser | None) -> bool:
    """disabled 模式下 optional_auth 返回匿名用户，公开分享接口一律按未认证处理，
    避免匿名访问者直接获得全书权限。"""
    return user is not None and settings.auth_mode != "disabled"


def _rate_limit(request: Request) -> None:
    if not share_rate_limiter.check(_client_ip(request)):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")


def _need_login_response() -> JSONResponse:
    """匿名读者触碰试读边界外章节 —— 绝不下发正文。"""
    return JSONResponse(
        status_code=403,
        content={
            "detail": "该章节超出试读范围，注册登录后即可阅读全书",
            "code": "need_login",
            "trial_ok": False,
        },
    )


def _public_view(share: dict, user: AuthUser | None) -> dict:
    """Share metadata safe to expose publicly."""
    authenticated = _is_authenticated(user)
    is_owner = authenticated and (
        user.code == share["owner_id"] or user.sub == share["owner_id"]
    )
    return {
        "id": share["id"],
        "title": share["title"],
        "author": share["author"],
        "intro": share["intro"],
        "genre": share["genre"],
        "cover": share["cover"],
        "trial_mode": share["trial_mode"],
        "trial_value": share["trial_value"],
        "chapter_count": share["chapter_count"],
        "word_count": share["word_count"],
        "view_count": share["view_count"],
        "read_count": share["read_count"],
        "created_at": share["created_at"],
        "access": {
            "authenticated": authenticated,
            "is_owner": is_owner,
            "level": "author" if is_owner else ("registered" if authenticated else "anonymous"),
        },
    }


# ══════════════════════════════════════════════════════════════
# 公开面
# ══════════════════════════════════════════════════════════════

@public_router.get("/share/{share_id}")
async def get_share_page(
    share_id: str,
    request: Request,
    user: AuthUser | None = Depends(optional_auth),
):
    _rate_limit(request)
    conn = await get_connection(settings.db_path)
    try:
        share = await store.get_active_share(conn, share_id)
        if share is None:
            raise HTTPException(status_code=404, detail="分享不存在或已关闭")
        await store.increment_view(conn, share_id)
        view = _public_view(share, user)
    finally:
        await conn.close()
    view["share_url"] = f"{settings.public_origin.rstrip('/')}/read/{share_id}"
    return view


@public_router.get("/share/{share_id}/chapters")
async def get_share_chapters(
    share_id: str,
    request: Request,
    user: AuthUser | None = Depends(optional_auth),
):
    _rate_limit(request)
    conn = await get_connection(settings.db_path)
    try:
        share = await store.get_active_share(conn, share_id)
        if share is None:
            raise HTTPException(status_code=404, detail="分享不存在或已关闭")
    finally:
        await conn.close()

    content = await load_novel_content(share["novel_id"])
    if content is None:
        raise HTTPException(status_code=404, detail="原作已被删除，无法阅读")

    chapter_words = [c.word_count for c in content.chapters]
    total = len(content.chapters)
    authenticated = _is_authenticated(user)
    trial_count = trial_chapter_count(
        trial_mode=share["trial_mode"],
        trial_value=share["trial_value"],
        total_chapters=total,
        chapter_words=chapter_words,
    )

    chapters = [
        {
            "chapter_index": c.index,
            "title": c.title,
            "word_count": c.word_count,
            "readable": is_chapter_readable(
                trial_mode=share["trial_mode"],
                trial_value=share["trial_value"],
                chapter_index=c.index,
                total_chapters=total,
                chapter_words=chapter_words,
                is_authenticated=authenticated,
            ),
        }
        for c in content.chapters
    ]
    return {
        "share_id": share_id,
        "total": total,
        "trial_chapter_count": trial_count,
        "authenticated": authenticated,
        "chapters": chapters,
    }


@public_router.get("/share/{share_id}/chapter/{chapter_index}")
async def get_share_chapter(
    share_id: str,
    chapter_index: int,
    request: Request,
    user: AuthUser | None = Depends(optional_auth),
):
    _rate_limit(request)
    conn = await get_connection(settings.db_path)
    try:
        share = await store.get_active_share(conn, share_id)
        if share is None:
            raise HTTPException(status_code=404, detail="分享不存在或已关闭")

        content = await load_novel_content(share["novel_id"])
        if content is None:
            raise HTTPException(status_code=404, detail="原作已被删除，无法阅读")

        chapter = next((c for c in content.chapters if c.index == chapter_index), None)
        if chapter is None:
            raise HTTPException(status_code=404, detail="章节不存在")

        chapter_words = [c.word_count for c in content.chapters]
        total = len(content.chapters)
        authenticated = _is_authenticated(user)

        if not is_chapter_readable(
            trial_mode=share["trial_mode"],
            trial_value=share["trial_value"],
            chapter_index=chapter_index,
            total_chapters=total,
            chapter_words=chapter_words,
            is_authenticated=authenticated,
        ):
            return _need_login_response()

        # 注册用户：记进度；阅读统计 +1
        if authenticated:
            user_code = user.code or user.sub
            await store.upsert_progress(
                conn,
                user_code=user_code,
                share_id=share_id,
                novel_id=share["novel_id"],
                chapter_index=chapter_index,
            )
        await store.increment_read(conn, share_id)
    finally:
        await conn.close()

    indices = [c.index for c in content.chapters]
    pos = indices.index(chapter.index)
    return {
        "share_id": share_id,
        "chapter_index": chapter.index,
        "title": chapter.title,
        "content": chapter.text,
        "word_count": chapter.word_count,
        "has_prev": pos > 0,
        "has_next": pos < len(indices) - 1,
        "next_index": indices[pos + 1] if pos < len(indices) - 1 else None,
        "prev_index": indices[pos - 1] if pos > 0 else None,
        "authenticated": authenticated,
    }


# ══════════════════════════════════════════════════════════════
# 作者面 / 读者面（需登录）
# ══════════════════════════════════════════════════════════════

class CreateShareRequest(BaseModel):
    novel_id: str
    trial_mode: str = "first_n_chapters"
    trial_value: int = Field(default=3, ge=0, le=10000)


class UpdateShareRequest(BaseModel):
    trial_mode: str | None = None
    trial_value: int | None = Field(default=None, ge=0, le=10000)
    status: str | None = None  # active | disabled


@router.post("/share")
async def create_share(req: CreateShareRequest, user: AuthUser = Depends(require_auth)):
    if req.trial_mode not in VALID_TRIAL_MODES:
        raise HTTPException(status_code=400, detail="trial_mode 非法")

    content = await load_novel_content(req.novel_id)
    if content is None:
        raise HTTPException(status_code=404, detail="未找到该小说")

    owner_id = user.code or user.sub
    conn = await get_connection(settings.db_path)
    try:
        # 同一作者对同一本书保持一个可复用的活跃分享（幂等）
        cursor = await conn.execute(
            "SELECT * FROM share_links WHERE novel_id = ? AND owner_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (req.novel_id, owner_id),
        )
        existing = await cursor.fetchone()
        if existing is not None:
            # 复用既有分享，但应用本次请求的试读设置（作者意图以最新请求为准）
            share = await store.update_share_settings(
                conn,
                existing["id"],
                owner_id,
                trial_mode=req.trial_mode,
                trial_value=req.trial_value,
            )
        else:
            share = await store.create_share(
                conn,
                novel_id=req.novel_id,
                owner_id=owner_id,
                title=content.title,
                intro=content.intro,
                genre=content.genre,
                author=owner_id,
                trial_mode=req.trial_mode,
                trial_value=req.trial_value,
                chapter_count=len(content.chapters),
                word_count=content.total_words,
            )
    finally:
        await conn.close()

    share["share_url"] = f"{settings.public_origin.rstrip('/')}/read/{share['id']}"
    return share


@router.get("/share/mine")
async def my_shares(user: AuthUser = Depends(require_auth)):
    owner_id = user.code or user.sub
    conn = await get_connection(settings.db_path)
    try:
        shares = await store.list_owner_shares(conn, owner_id)
    finally:
        await conn.close()
    for share in shares:
        share["share_url"] = f"{settings.public_origin.rstrip('/')}/read/{share['id']}"
    return {"shares": shares}


@router.patch("/share/{share_id}")
async def update_share(
    share_id: str,
    req: UpdateShareRequest,
    user: AuthUser = Depends(require_auth),
):
    if req.trial_mode is not None and req.trial_mode not in VALID_TRIAL_MODES:
        raise HTTPException(status_code=400, detail="trial_mode 非法")
    if req.status is not None and req.status not in ("active", "disabled"):
        raise HTTPException(status_code=400, detail="status 必须是 active/disabled")

    conn = await get_connection(settings.db_path)
    try:
        share = await store.update_share_settings(
            conn,
            share_id,
            user.code or user.sub,
            trial_mode=req.trial_mode,
            trial_value=req.trial_value,
            status=req.status,
            is_admin=user.is_admin,
        )
    finally:
        await conn.close()

    if share is None:
        raise HTTPException(status_code=404, detail="分享不存在或无权管理")
    return share


@router.get("/bookshelf")
async def my_bookshelf(user: AuthUser = Depends(require_auth)):
    conn = await get_connection(settings.db_path)
    try:
        items = await store.list_bookshelf(conn, user.code or user.sub)
    finally:
        await conn.close()
    return {"books": items}


class ProgressRequest(BaseModel):
    share_id: str
    chapter_index: int = Field(ge=0)


@router.post("/bookshelf/progress")
async def report_progress(req: ProgressRequest, user: AuthUser = Depends(require_auth)):
    conn = await get_connection(settings.db_path)
    try:
        share = await store.get_active_share(conn, req.share_id)
        if share is None:
            raise HTTPException(status_code=404, detail="分享不存在或已关闭")
        await store.upsert_progress(
            conn,
            user_code=user.code or user.sub,
            share_id=req.share_id,
            novel_id=share["novel_id"],
            chapter_index=req.chapter_index,
        )
    finally:
        await conn.close()
    return {"ok": True}
