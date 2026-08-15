"""Share & reader routes (Milestone 15, Requirement B).

Public reading surface (anonymous OK):
  GET  /share/{share_id}              — share page metadata (snapshot)
  GET  /share/{share_id}/chapters     — TOC with per-chapter readable flag
  GET  /share/{share_id}/chapter/{n}  — chapter body (trial gate for anonymous)
  POST /share/{share_id}/conversion   — trial→registered conversion event (auth)

Author surface (require_auth + owner):
  POST   /share                 — create / re-activate a share for a novel
  GET    /shares                — my shares + stats
  PATCH  /share/{share_id}      — trial policy / status / snapshot edits
  DELETE /share/{share_id}      — disable the share (all public endpoints 404)

Registered reader surface (require_auth):
  GET /bookshelf                        — bookshelf + progress
  PUT /bookshelf/{novel_id}             — add/remove from bookshelf
  GET /share/{share_id}/progress        — my reading progress
  PUT /share/{share_id}/progress        — update progress

Security model (needs doc §4.6):
- backend is the single source of truth — bodies only leave through the
  permission-checked endpoint below; the frontend never receives hidden chapters
- anonymous requests beyond the trial edge get ``403 {code: need_login}``
  and **no content**
- disabled share ⇒ every public endpoint returns 404
- public share endpoints are rate-limited (60 req/min per IP)
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from novel_creator.config import settings
from novel_creator.memory import share_store
from novel_creator.memory.database import get_connection
from novel_creator.memory.registry import get_novel_by_id
from novel_creator.web.auth_deps import AuthUser, optional_auth, require_auth
from novel_creator.web.rate_limit import enforce, share_limiter

router = APIRouter()  # public reading surface
protected_router = APIRouter(dependencies=[Depends(require_auth)])  # author + reader

# In-memory UV dedup: (share_id, date, visitor_hash); bounded
_seen_visitors: set[str] = set()
_UV_SET_CAP = 200_000


def _user_key(user: AuthUser) -> str:
    """Stable identity key: invite code (jwt) / Casdoor sub / anonymous."""
    return user.code or user.sub or "anonymous"


def _is_owner(user: AuthUser, share: dict) -> bool:
    return user.is_admin or share["owner_id"] == _user_key(user)


def _visitor_hash(request: Request) -> str:
    ua = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else ""
    return hashlib.sha256(f"{ip}|{ua}".encode()).hexdigest()[:16]


async def _get_active_share_or_404(share_id: str) -> dict:
    conn = await get_connection(settings.db_path)
    try:
        share = await share_store.get_active_share(conn, share_id)
    finally:
        await conn.close()
    if share is None:
        # Do not distinguish "unknown" vs "disabled" (no existence probing)
        raise HTTPException(status_code=404, detail="分享不存在或已关闭")
    return share


async def _load_novel_chapters(db_path: str) -> tuple[list[dict], list[dict]]:
    """Read chapter list + volumes from a novel DB.

    Returns (chapters, volumes) where chapter items carry
    ``chapter_index/title/word_count/scene_count``.
    """
    conn = await get_connection(db_path)
    try:
        cursor = await conn.execute(
            """SELECT chapter_index, title,
                      SUM(LENGTH(content)) AS word_count,
                      COUNT(*) AS scene_count,
                      SUM(CASE WHEN TRIM(content) = '' THEN 1 ELSE 0 END) AS empty_scenes
               FROM chapter_texts
               GROUP BY chapter_index
               ORDER BY chapter_index"""
        )
        chapters = [dict(r) for r in await cursor.fetchall()]
        cursor = await conn.execute(
            "SELECT volume_index, title, chapter_start, chapter_end "
            "FROM volumes ORDER BY volume_index"
        )
        volumes = [dict(r) for r in await cursor.fetchall()]
    finally:
        await conn.close()
    return chapters, volumes


def _trial_allowed_chapter_count(share: dict, chapters: list[dict]) -> int:
    """Number of leading chapters readable anonymously under the trial policy."""
    mode = share["trial_mode"]
    value = share["trial_value"]
    total = len(chapters)
    if total == 0:
        return 0
    if mode == share_store.TRIAL_MODE_WORD_COUNT:
        budget = max(0, value)
        cumulative = 0
        for i, ch in enumerate(chapters):
            if cumulative + ch["word_count"] > budget and i > 0:
                return i
            cumulative += ch["word_count"]
            if cumulative >= budget:
                return i + 1
        return total
    if mode == share_store.TRIAL_MODE_RATIO:
        pct = min(max(value, 0), 100)
        return math.ceil(total * pct / 100)
    # default: first_n_chapters
    return min(max(value, 0), total)


def _public_share_view(share: dict) -> dict:
    """Metadata exposed on the public share page (no owner identity)."""
    return {
        "share_id": share["id"],
        "novel_id": share["novel_id"],
        "title": share["title_snapshot"],
        "cover": share["cover_snapshot"],
        "intro": share["intro_snapshot"],
        "trial_mode": share["trial_mode"],
        "trial_value": share["trial_value"],
        "created_at": share["created_at"],
    }


def _need_login_response() -> HTTPException:
    """越权响应约定 (§4.5): 403 + need_login, never any body content."""
    return HTTPException(
        status_code=403,
        detail={"code": "need_login", "trial_ok": False, "message": "注册后即可阅读全文"},
    )


# ══════════════════════════════════════════════════════════════
# Public reading surface
# ══════════════════════════════════════════════════════════════


@router.get("/share/{share_id}")
async def get_share_page(share_id: str, request: Request):
    """Share page metadata — cover / title / intro snapshot + chapter count."""
    enforce(share_limiter, request, scope="share")
    share = await _get_active_share_or_404(share_id)

    novel = get_novel_by_id(share["novel_id"])
    chapter_count = 0
    status_ = "ok"
    if novel is not None:
        chapters, _ = await _load_novel_chapters(novel.db_path)
        chapter_count = len(chapters)
    else:
        status_ = "novel_missing"

    # PV + UV bookkeeping
    conn = await get_connection(settings.db_path)
    try:
        await share_store.bump_share_counter(conn, share_id, "view_count")
        visitor = _visitor_hash(request)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"{share_id}|{today}|{visitor}"
        new_visitor = False
        if key not in _seen_visitors:
            new_visitor = True
            if len(_seen_visitors) < _UV_SET_CAP:
                _seen_visitors.add(key)
        await share_store.record_daily_stat(
            conn, share_id, views=1, new_visitor=new_visitor
        )
    finally:
        await conn.close()

    return {
        **_public_share_view(share),
        "chapter_count": chapter_count,
        "status": status_,
    }


@router.get("/share/{share_id}/chapters")
async def get_share_chapters(
    share_id: str,
    request: Request,
    user: Optional[AuthUser] = Depends(optional_auth),
):
    """TOC — public, each chapter marked readable or locked for THIS visitor.

    后端只暴露权限判定结果；试读外章节的正文绝不出现在响应里。
    """
    enforce(share_limiter, request, scope="share")
    share = await _get_active_share_or_404(share_id)

    novel = get_novel_by_id(share["novel_id"])
    if novel is None:
        raise HTTPException(status_code=404, detail="小说不存在")

    chapters, volumes = await _load_novel_chapters(novel.db_path)

    # 注册即全文（开源版）：require_auth 通过的用户 + 分享所有者 → 全文
    has_full_access = user is not None
    trial_n = _trial_allowed_chapter_count(share, chapters)

    items = []
    for ch in chapters:
        readable = has_full_access or ch["chapter_index"] < trial_n
        items.append(
            {
                "chapter_index": ch["chapter_index"],
                "title": ch["title"] or f"第{ch['chapter_index'] + 1}章",
                "word_count": ch["word_count"] or 0,
                "readable": readable,
            }
        )

    return {
        "share_id": share_id,
        "novel_id": share["novel_id"],
        "title": share["title_snapshot"],
        "has_full_access": bool(has_full_access),
        "trial_chapters": trial_n if not has_full_access else len(chapters),
        "volumes": volumes,
        "chapters": items,
    }


def _is_owner_or_analytics(user: Optional[AuthUser], share: dict) -> bool:
    return bool(user is not None and _is_owner(user, share))


async def _read_chapter_body(db_path: str, chapter_index: int) -> Optional[dict]:
    """Fetch one chapter's joined body text from the novel DB."""
    conn = await get_connection(db_path)
    try:
        cursor = await conn.execute(
            """SELECT title, content, summary FROM chapter_texts
               WHERE chapter_index = ? ORDER BY scene_index""",
            (chapter_index,),
        )
        rows = await cursor.fetchall()
    finally:
        await conn.close()
    if not rows:
        return None
    title = rows[0]["title"] or ""
    summary = rows[0]["summary"] or ""
    content = "\n\n".join(r["content"] for r in rows)
    return {
        "chapter_index": chapter_index,
        "title": title,
        "summary": summary,
        "content": content,
        "word_count": len(content),
    }


def _apply_watermark(content: str, user: AuthUser) -> str:
    """Optional leak-tracing watermark (off by default, NOVEL_SHARE_WATERMARK)."""
    if not settings.share_watermark:
        return content
    key = _user_key(user)
    return f"{content}\n\n〔WorldNovel 阅读印记 · {key}〕"


@router.get("/share/{share_id}/chapter/{chapter_index}")
async def get_share_chapter(
    share_id: str,
    chapter_index: int,
    request: Request,
    user: Optional[AuthUser] = Depends(optional_auth),
):
    """Chapter body.

    - owner / 注册用户（require_auth 通过）→ 全文
    - 匿名 → 仅试读边界内；边界外 403 need_login（无正文）
    """
    enforce(share_limiter, request, scope="share")
    share = await _get_active_share_or_404(share_id)

    novel = get_novel_by_id(share["novel_id"])
    if novel is None:
        raise HTTPException(status_code=404, detail="小说不存在")

    chapters, _ = await _load_novel_chapters(novel.db_path)
    valid_index = {c["chapter_index"] for c in chapters}
    if chapter_index not in valid_index:
        raise HTTPException(status_code=404, detail="章节不存在")

    is_owner = _is_owner_or_analytics(user, share)
    is_registered = user is not None
    if not (is_owner or is_registered):
        trial_n = _trial_allowed_chapter_count(share, chapters)
        if chapter_index >= trial_n:
            # 越权：绝不下发正文
            raise _need_login_response()

    body = await _read_chapter_body(novel.db_path, chapter_index)
    if body is None:
        raise HTTPException(status_code=404, detail="章节不存在")

    if user is not None and not is_owner:
        body["content"] = _apply_watermark(body["content"], user)

    # reads stat + auto progress for registered readers
    conn = await get_connection(settings.db_path)
    try:
        await share_store.bump_share_counter(conn, share_id, "read_count")
        await share_store.record_daily_stat(conn, share_id, reads=1)
        if user is not None:
            await share_store.upsert_progress(
                conn,
                user_code=_user_key(user),
                novel_id=share["novel_id"],
                chapter_index=chapter_index,
                share_id=share_id,
            )
    finally:
        await conn.close()

    return {
        "share_id": share_id,
        "novel_id": share["novel_id"],
        "chapter_count": len(chapters),
        **body,
    }


class ConversionRequest(BaseModel):
    """Trial→registered conversion beacon (idempotent)."""

    ref: str = ""  # optional referrer share id carried through login redirect


@protected_router.post("/share/{share_id}/conversion")
async def share_conversion(share_id: str, req: ConversionRequest, user: AuthUser = Depends(require_auth)):
    """Registered user reports they came from this share — conversion metric."""
    conn = await get_connection(settings.db_path)
    try:
        share = await share_store.get_active_share(conn, share_id)
        if share is None:
            raise HTTPException(status_code=404, detail="分享不存在或已关闭")
        recorded = await share_store.record_conversion(
            conn, share_id, _user_key(user)
        )
    finally:
        await conn.close()
    return {"ok": True, "recorded": recorded}


# ══════════════════════════════════════════════════════════════
# Author surface
# ══════════════════════════════════════════════════════════════


class CreateShareRequest(BaseModel):
    novel_id: str
    trial_mode: str = share_store.TRIAL_MODE_FIRST_N
    trial_value: int = Field(default=3, ge=0)


@protected_router.post("/share")
async def create_share(req: CreateShareRequest, user: AuthUser = Depends(require_auth)):
    """Create (or re-activate) the share link for a novel.

    Metadata snapshot is captured now so later edits to the source novel do not
    break an already-shared page (§4.3).
    """
    novel = get_novel_by_id(req.novel_id)
    if novel is None:
        raise HTTPException(status_code=404, detail="小说不存在")

    # Build snapshot: title from registry, intro from outline premise/setting
    import json as _json

    title = novel.title
    intro = ""
    try:
        conn_novel = await get_connection(novel.db_path)
        try:
            cursor = await conn_novel.execute(
                "SELECT outline_json FROM story_outline WHERE id = 1"
            )
            row = await cursor.fetchone()
            if row:
                outline = _json.loads(row["outline_json"])
                title = outline.get("title", title)
                parts = [
                    outline.get("premise", ""),
                    outline.get("setting", ""),
                ]
                intro = "\n\n".join(p for p in parts if p)
        finally:
            await conn_novel.close()
    except Exception:
        pass

    conn = await get_connection(settings.db_path)
    try:
        share = await share_store.create_share(
            conn,
            novel_id=req.novel_id,
            owner_id=_user_key(user),
            title=title,
            cover="",
            intro=intro,
            trial_mode=req.trial_mode,
            trial_value=req.trial_value,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await conn.close()

    public_origin = settings.public_origin.rstrip("/")
    return {
        "ok": True,
        **_author_share_view(share),
        "share_url": f"{public_origin}/read/{share['id']}",
    }


def _author_share_view(share: dict) -> dict:
    return {
        "share_id": share["id"],
        "novel_id": share["novel_id"],
        "owner_id": share["owner_id"],
        "title": share["title_snapshot"],
        "intro": share["intro_snapshot"],
        "trial_mode": share["trial_mode"],
        "trial_value": share["trial_value"],
        "status": share["status"],
        "view_count": share["view_count"],
        "read_count": share["read_count"],
        "register_count": share["register_count"],
        "created_at": share["created_at"],
        "disabled_at": share["disabled_at"],
    }


@protected_router.get("/shares")
async def list_my_shares(user: AuthUser = Depends(require_auth)):
    """Author's share management list with per-share totals."""
    conn = await get_connection(settings.db_path)
    try:
        shares = await share_store.list_shares_for_owner(conn, _user_key(user))
    finally:
        await conn.close()
    public_origin = settings.public_origin.rstrip("/")
    return {
        "shares": [
            {
                **_author_share_view(s),
                "share_url": f"{public_origin}/read/{s['id']}",
            }
            for s in shares
        ]
    }


class PatchShareRequest(BaseModel):
    trial_mode: Optional[str] = None
    trial_value: Optional[int] = Field(default=None, ge=0)
    status: Optional[str] = None  # active | disabled
    title: Optional[str] = None
    intro: Optional[str] = None


@protected_router.patch("/share/{share_id}")
async def patch_share(share_id: str, req: PatchShareRequest, user: AuthUser = Depends(require_auth)):
    """Owner-only: change trial policy / disable / edit snapshot. 即时生效."""
    conn = await get_connection(settings.db_path)
    try:
        share = await share_store.get_share(conn, share_id)
        if share is None:
            raise HTTPException(status_code=404, detail="分享不存在")
        if not _is_owner(user, share):
            raise HTTPException(status_code=403, detail="无权管理该分享")
        try:
            await share_store.update_share(
                conn,
                share_id,
                trial_mode=req.trial_mode,
                trial_value=req.trial_value,
                title=req.title,
                intro=req.intro,
            )
            if req.status is not None:
                await share_store.set_share_status(conn, share_id, req.status)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        share = await share_store.get_share(conn, share_id)
    finally:
        await conn.close()
    return {"ok": True, **_author_share_view(share)}


@protected_router.delete("/share/{share_id}")
async def disable_share(share_id: str, user: AuthUser = Depends(require_auth)):
    """Owner-only: disable share — all public endpoints immediately 404."""
    conn = await get_connection(settings.db_path)
    try:
        share = await share_store.get_share(conn, share_id)
        if share is None:
            raise HTTPException(status_code=404, detail="分享不存在")
        if not _is_owner(user, share):
            raise HTTPException(status_code=403, detail="无权管理该分享")
        await share_store.set_share_status(conn, share_id, "disabled")
    finally:
        await conn.close()
    return {"ok": True}


@protected_router.get("/share/{share_id}/stats")
async def share_stats(share_id: str, days: int = 30, user: AuthUser = Depends(require_auth)):
    """Owner-only analytics: totals + daily PV/reads/UV + conversion."""
    conn = await get_connection(settings.db_path)
    try:
        share = await share_store.get_share(conn, share_id)
        if share is None:
            raise HTTPException(status_code=404, detail="分享不存在")
        if not _is_owner(user, share):
            raise HTTPException(status_code=403, detail="无权查看该分享数据")
        daily = await share_store.get_share_stats(conn, share_id, days=days)
    finally:
        await conn.close()
    return {
        "share_id": share_id,
        "view_count": share["view_count"],
        "read_count": share["read_count"],
        "register_count": share["register_count"],
        "daily": daily,
    }


# ══════════════════════════════════════════════════════════════
# Registered reader surface — bookshelf & progress
# ══════════════════════════════════════════════════════════════


@protected_router.get("/bookshelf")
async def get_bookshelf(user: AuthUser = Depends(require_auth)):
    """Registered user's bookshelf with progress + novel metadata."""
    conn = await get_connection(settings.db_path)
    try:
        entries = await share_store.list_bookshelf(conn, _user_key(user))
    finally:
        await conn.close()

    items = []
    for e in entries:
        novel = get_novel_by_id(e["novel_id"])
        if novel is None:
            continue  # novel deleted — skip silently
        items.append(
            {
                "novel_id": e["novel_id"],
                "title": novel.title,
                "genre": novel.genre,
                "share_id": e["share_id"],
                "chapter_index": e["chapter_index"],
                "last_read_at": e["last_read_at"],
            }
        )
    return {"bookshelf": items}


class BookshelfRequest(BaseModel):
    in_bookshelf: bool = True
    share_id: str = ""


@protected_router.put("/bookshelf/{novel_id}")
async def update_bookshelf(novel_id: str, req: BookshelfRequest, user: AuthUser = Depends(require_auth)):
    conn = await get_connection(settings.db_path)
    try:
        await share_store.set_bookshelf(
            conn,
            user_code=_user_key(user),
            novel_id=novel_id,
            in_bookshelf=req.in_bookshelf,
            share_id=req.share_id,
        )
    finally:
        await conn.close()
    return {"ok": True}


@protected_router.get("/share/{share_id}/progress")
async def get_my_progress(share_id: str, user: AuthUser = Depends(require_auth)):
    conn = await get_connection(settings.db_path)
    try:
        share = await share_store.get_share(conn, share_id)
        if share is None:
            raise HTTPException(status_code=404, detail="分享不存在")
        progress = await share_store.get_progress(
            conn, _user_key(user), share["novel_id"]
        )
    finally:
        await conn.close()
    return {
        "novel_id": share["novel_id"],
        "chapter_index": progress["chapter_index"] if progress else 0,
        "in_bookshelf": bool(progress and progress["in_bookshelf"]),
    }


class ProgressRequest(BaseModel):
    chapter_index: int = Field(ge=0)


@protected_router.put("/share/{share_id}/progress")
async def update_my_progress(share_id: str, req: ProgressRequest, user: AuthUser = Depends(require_auth)):
    conn = await get_connection(settings.db_path)
    try:
        share = await share_store.get_share(conn, share_id)
        if share is None:
            raise HTTPException(status_code=404, detail="分享不存在")
        await share_store.upsert_progress(
            conn,
            user_code=_user_key(user),
            novel_id=share["novel_id"],
            chapter_index=req.chapter_index,
            share_id=share_id,
        )
    finally:
        await conn.close()
    return {"ok": True}
