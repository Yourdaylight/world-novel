"""Public share + register-to-read routes — requirement B.

Public (rate-limited, optional auth):
  GET /share/{id}            share-page metadata snapshot
  GET /share/{id}/chapters   TOC with a per-chapter ``readable`` flag
  GET /share/{id}/chapter/{n} chapter body — trial window for anonymous,
                             full text for any registered user; 403 otherwise

Author management (require_auth):
  POST /share                create / fetch the active share for a novel
  GET  /shares/mine          list the caller's shares (plural to avoid the
                             /share/{id} path collision)
  PATCH /share/{id}          change trial policy or disable (owner/admin)

Registered reader:
  GET /bookshelf             reading-progress list

Security: the backend is the only gate. Chapter text beyond the trial window
is *never* serialised for an anonymous request — not even hidden in payload.
"""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from novel_creator.config import settings
from novel_creator.memory.database import get_connection
from novel_creator.memory import share_store
from novel_creator.memory.registry import get_novel_by_id

from ..auth_deps import AuthUser, optional_auth, require_auth
from ..book import Book, BookNotFound, load_book
from ..ratelimit import client_key, share_limiter
from ._helpers import can_manage_novel

# Public reader surface (no login required).
router = APIRouter()
# Author/reader management (login required).
protected_router = APIRouter(dependencies=[Depends(require_auth)])


# ── Trial policy ──────────────────────────────────────────────────────────

def chapter_in_trial(
    share: dict,
    chapter_index: int,
    total_chapters: int,
    cumulative_words: int,
    total_words: int,
) -> bool:
    """Whether ``chapter_index`` (0-based) is inside the anonymous trial window."""
    mode = share.get("trial_mode", "first_n_chapters")
    value = share.get("trial_value", 3)
    if mode == "word_count":
        return cumulative_words <= max(0, value)
    if mode == "ratio":
        ratio = min(max(float(value or 0) / 100.0, 0.0), 1.0)
        n_trial = max(0, math.ceil(total_chapters * ratio))
        return chapter_index < n_trial
    # default: first_n_chapters
    return chapter_index < max(0, int(value or 0))


async def _rate_limit(request: Request) -> None:
    allowed, retry_after = share_limiter.check(f"share:{client_key(request.scope)}")
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="请求过于频繁，请稍后再试",
            headers={"Retry-After": str(retry_after)},
        )


def _public_meta(share: dict, *, authed: bool, chapters_total: int) -> dict:
    """Metadata safe to expose on the public reader page."""
    meta = share.get("meta") or {}
    return {
        "id": share["id"],
        "title": share.get("title", ""),
        "intro": share.get("intro", ""),
        "cover": share.get("cover", ""),
        "genre": meta.get("genre", ""),
        "author": meta.get("author", ""),
        "chapters_total": chapters_total or meta.get("chapters_total", 0),
        "trial_mode": share.get("trial_mode", "first_n_chapters"),
        "trial_value": share.get("trial_value", 3),
        "view_count": share.get("view_count", 0),
        "read_count": share.get("read_count", 0),
        "authenticated": authed,
        "can_read_full": authed,  # open-source: register = full access
    }


async def _load_active_share(conn, share_id: str) -> dict:
    share = await share_store.get_share(conn, share_id, only_active=True)
    if share is None:
        # 404 for both unknown and disabled shares — never reveal which.
        raise HTTPException(status_code=404, detail="分享不存在或已关闭")
    return share


# ── Public reader endpoints ───────────────────────────────────────────────

@router.get("/share/{share_id}")
async def public_share_meta(
    share_id: str,
    request: Request,
    user: AuthUser | None = Depends(optional_auth),
    _rl: None = Depends(_rate_limit),
):
    """Share-page metadata (cover / intro / trial config)."""
    conn = await get_connection(settings.db_path)
    try:
        share = await _load_active_share(conn, share_id)
        await share_store.increment_view(conn, share_id)
        total = len(_safe_chapter_indices(share))
    finally:
        await conn.close()
    authed = user is not None
    return _public_meta(share, authed=authed, chapters_total=total)


@router.get("/share/{share_id}/chapters")
async def public_share_chapters(
    share_id: str,
    request: Request,
    user: AuthUser | None = Depends(optional_auth),
    _rl: None = Depends(_rate_limit),
):
    """TOC with per-chapter readable flag — no body text."""
    conn = await get_connection(settings.db_path)
    try:
        share = await _load_active_share(conn, share_id)
        # The reader SPA loads this endpoint (not bare meta) on page open.
        await share_store.increment_view(conn, share_id)
    finally:
        await conn.close()

    try:
        book = await load_book(share["novel_id"])
    except BookNotFound:
        raise HTTPException(status_code=404, detail="分享不存在或已关闭")

    authed = user is not None
    cumulative = 0
    toc = []
    for ch in book.chapters:
        cumulative += ch.word_count
        readable = authed or chapter_in_trial(
            share, ch.chapter_index, len(book.chapters), cumulative, book.total_words
        )
        toc.append({
            "chapter_index": ch.chapter_index,
            "title": ch.title,
            "word_count": ch.word_count,
            "readable": readable,
        })
    return {
        "meta": _public_meta(share, authed=authed, chapters_total=len(book.chapters)),
        "chapters": toc,
    }


@router.get("/share/{share_id}/chapter/{chapter_index}")
async def public_share_chapter(
    share_id: str,
    chapter_index: int,
    request: Request,
    user: AuthUser | None = Depends(optional_auth),
    _rl: None = Depends(_rate_limit),
):
    """Chapter body. Anonymous requests past the trial window get 403."""
    conn = await get_connection(settings.db_path)
    try:
        share = await _load_active_share(conn, share_id)
    finally:
        await conn.close()

    try:
        book = await load_book(share["novel_id"])
    except BookNotFound:
        raise HTTPException(status_code=404, detail="分享不存在或已关闭")

    chapter = next(
        (c for c in book.chapters if c.chapter_index == chapter_index), None
    )
    if chapter is None:
        raise HTTPException(status_code=404, detail="章节不存在")

    authed = user is not None
    cumulative = sum(c.word_count for c in book.chapters if c.chapter_index <= chapter_index)
    in_trial = chapter_in_trial(
        share, chapter_index, len(book.chapters), cumulative, book.total_words
    )

    next_chapter = next(
        (c for c in book.chapters if c.chapter_index == chapter_index + 1), None
    )
    next_locked = bool(
        not authed
        and next_chapter is not None
        and not chapter_in_trial(
            share, chapter_index + 1, len(book.chapters),
            cumulative + next_chapter.word_count, book.total_words,
        )
    )

    if not authed and not in_trial:
        # The gate: no body text is ever returned beyond the trial window.
        raise HTTPException(
            status_code=403,
            detail={
                "code": "need_login",
                "trial_ok": False,
                "message": "试读到这里，注册后即可阅读全部章节",
                "chapter_index": chapter_index,
            },
        )

    conn = await get_connection(settings.db_path)
    try:
        await share_store.increment_read(conn, share_id)
        if authed:
            identity = user.code or user.sub or "anonymous"
            await share_store.upsert_progress(
                conn,
                user_code=identity,
                share_id=share_id,
                novel_id=share["novel_id"],
                chapter_index=chapter_index,
            )
    finally:
        await conn.close()

    return {
        "chapter_index": chapter.chapter_index,
        "title": chapter.title,
        "text": chapter.text,
        "word_count": chapter.word_count,
        "authenticated": authed,
        "next_locked": next_locked,
    }


def _safe_chapter_indices(share: dict) -> list[int]:
    """Best-effort chapter count from the snapshot meta (no novel-db access)."""
    meta = share.get("meta") or {}
    try:
        return list(range(int(meta.get("chapters_total", 0))))
    except (TypeError, ValueError):
        return []


# ── Author management ─────────────────────────────────────────────────────

class CreateShareRequest(BaseModel):
    novel_id: str | None = None
    trial_mode: str = Field(default="first_n_chapters")
    trial_value: int = Field(default=3, ge=0, le=100000)


class UpdateShareRequest(BaseModel):
    trial_mode: str | None = None
    trial_value: int | None = Field(default=None, ge=0, le=100000)
    status: str | None = None  # active | disabled


def _identity(user: AuthUser) -> str:
    return user.code or user.sub or "anonymous"


@protected_router.post("/share")
async def create_share(req: CreateShareRequest, user: AuthUser = Depends(require_auth)):
    """Create (or return the existing active) share for a novel."""
    if req.trial_mode not in ("first_n_chapters", "word_count", "ratio"):
        raise HTTPException(status_code=400, detail="非法试读模式")
    target = req.novel_id or _active_novel_id()
    novel = get_novel_by_id(target)
    if novel is None:
        raise HTTPException(status_code=404, detail="未找到小说")
    if not can_manage_novel(novel, user):
        raise HTTPException(status_code=403, detail="无权分享他人的小说")
    try:
        book: Book = await load_book(target)
    except BookNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    owner = _identity(user)
    conn = await get_connection(settings.db_path)
    try:
        existing = await share_store.list_active_share_for_novel(conn, target, owner)
        if existing is not None:
            return {"ok": True, "share": _owner_view(existing), "reused": True}
        share = await share_store.create_share(
            conn,
            novel_id=target,
            owner_id=owner,
            title=book.title,
            intro=book.intro,
            meta={
                "genre": book.genre,
                "chapters_total": len(book.chapters),
                "words_total": book.total_words,
            },
            trial_mode=req.trial_mode,
            trial_value=req.trial_value,
        )
    finally:
        await conn.close()
    return {"ok": True, "share": _owner_view(share)}


@protected_router.get("/shares/mine")
async def my_shares(user: AuthUser = Depends(require_auth)):
    conn = await get_connection(settings.db_path)
    try:
        shares = await share_store.list_shares_by_owner(conn, _identity(user))
    finally:
        await conn.close()
    return {"shares": [_owner_view(s) for s in shares]}


@protected_router.patch("/share/{share_id}")
async def update_share(
    share_id: str, req: UpdateShareRequest, user: AuthUser = Depends(require_auth)
):
    if req.status is not None and req.status not in ("active", "disabled"):
        raise HTTPException(status_code=400, detail="非法状态")
    if req.trial_mode is not None and req.trial_mode not in (
        "first_n_chapters", "word_count", "ratio"
    ):
        raise HTTPException(status_code=400, detail="非法试读模式")

    conn = await get_connection(settings.db_path)
    try:
        share = await share_store.get_share(conn, share_id)
        if share is None:
            raise HTTPException(status_code=404, detail="分享不存在")
        if not (user.is_admin or share["owner_id"] == _identity(user)):
            raise HTTPException(status_code=403, detail="无权操作他人的分享")
        ok = await share_store.update_share(
            conn,
            share_id,
            trial_mode=req.trial_mode,
            trial_value=req.trial_value,
            status=req.status,
        )
        share = await share_store.get_share(conn, share_id)
    finally:
        await conn.close()
    if not ok:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    return {"ok": True, "share": _owner_view(share)}


@protected_router.get("/bookshelf")
async def my_bookshelf(user: AuthUser = Depends(require_auth)):
    conn = await get_connection(settings.db_path)
    try:
        items = await share_store.list_progress(conn, _identity(user))
    finally:
        await conn.close()
    return {"items": items}


def _owner_view(share: dict) -> dict:
    """Full share row for the owner (includes novel_id, stats, policy)."""
    meta = share.get("meta") or {}
    return {
        "id": share["id"],
        "novel_id": share["novel_id"],
        "title": share.get("title", ""),
        "status": share.get("status", "active"),
        "trial_mode": share.get("trial_mode", "first_n_chapters"),
        "trial_value": share.get("trial_value", 3),
        "view_count": share.get("view_count", 0),
        "read_count": share.get("read_count", 0),
        "created_at": share.get("created_at", ""),
        "disabled_at": share.get("disabled_at"),
        "genre": meta.get("genre", ""),
        "chapters_total": meta.get("chapters_total", 0),
    }


def _active_novel_id() -> str:
    from novel_creator.memory.registry import get_active_novel
    active = get_active_novel()
    return active.novel_id if active else ""
