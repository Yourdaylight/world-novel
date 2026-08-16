"""Share routes — 公开分享 + 注册阅读（需求 B）。

权限模型（开源版「注册即全文」，无付费）：
  - 匿名访客：元数据/目录 + 试读章节（默认前 3 章，作者可配置）
  - 注册用户（require_auth 通过，jwt 邀请码 / casdoor sidecar 均可）：全文
  - 作者本人：分享管理（创建/关闭/试读策略/统计）

安全要点：
  - 正文只经本章单章接口按权限下发，接口绝不返回整本正文；
  - 公开响应不包含 novel_id / owner_id / 服务器路径；
  - 分享 ID 为 8 位随机短码（不可枚举），公开接口限流（rate_limit.py）；
  - 关闭分享后所有公开接口立即 404。
"""

from __future__ import annotations

import math
import secrets
import sqlite3

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from novel_creator.config import settings
from novel_creator.memory.database import get_connection
from novel_creator.memory.registry import get_novel_by_id
from novel_creator.web.auth_deps import (
    AuthUser,
    optional_auth_header,
    require_auth,
)
from novel_creator.web.book_service import Book, load_book_by_id
from novel_creator.web.rate_limit import share_rate_limit

# 公开阅读接口（限流）
router = APIRouter(dependencies=[Depends(share_rate_limit)])
# 作者/读者控制台接口（需登录）
protected_router = APIRouter(dependencies=[Depends(require_auth)])

_TRIAL_MODES = {"first_n_chapters", "word_count", "ratio", "all"}
_SHARE_ID_BYTES = 6  # token_urlsafe(6) → 8 字符短码


# ── helpers ───────────────────────────────────────────────────────────────

def _validate_trial(mode: str, value: int) -> tuple[str, int]:
    if mode not in _TRIAL_MODES:
        mode = "first_n_chapters"
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = 3
    if mode == "first_n_chapters":
        value = max(0, min(value, 100000))
    elif mode == "ratio":
        value = max(0, min(value, 100))
    elif mode == "word_count":
        value = max(0, min(value, 100_000_000))
    return mode, value


def chapter_readable(
    index: int,
    total_chapters: int,
    total_words: int,
    cum_words_before: int,
    mode: str,
    value: int,
    authed: bool,
) -> bool:
    """权限判定的唯一真相源：注册用户全文；匿名按试读策略。"""
    if authed:
        return True
    if mode == "all":
        return True
    if mode == "first_n_chapters":
        return index < value
    if mode == "ratio":
        n_open = math.ceil(total_chapters * value / 100) if total_chapters else 0
        return index < n_open
    if mode == "word_count":
        return cum_words_before < value
    return False


async def _fetch_share(conn, share_id: str) -> object | None:
    cursor = await conn.execute(
        "SELECT * FROM share_links WHERE id = ? AND status = 'active'", (share_id,)
    )
    return await cursor.fetchone()


def _share_meta(row, *, authed: bool, total_chapters: int) -> dict:
    """公开元数据——刻意不含 novel_id/owner_id。"""
    mode, value = row["trial_mode"], row["trial_value"]
    if authed or mode == "all":
        trial_open = total_chapters
    elif mode == "first_n_chapters":
        trial_open = min(value, total_chapters)
    elif mode == "ratio":
        trial_open = math.ceil(total_chapters * value / 100) if total_chapters else 0
    else:
        trial_open = None  # word_count：目录接口按累计字数逐章标记
    return {
        "id": row["id"],
        "title": row["title_snapshot"],
        "intro": row["intro_snapshot"],
        "genre": row["genre_snapshot"],
        "trial_mode": mode,
        "trial_value": value,
        "trial_open_chapters": trial_open,
        "chapters_total": total_chapters,
        "authed": authed,
        "can_read_all": authed,
        "stats": {"views": row["view_count"], "reads": row["read_count"]},
        "created_at": row["created_at"],
    }


# ── 作者：分享管理 ────────────────────────────────────────────────────────

class CreateShareRequest(BaseModel):
    novel_id: str
    trial_mode: str = "first_n_chapters"
    trial_value: int = 3


class PatchShareRequest(BaseModel):
    trial_mode: str | None = None
    trial_value: int | None = None
    status: str | None = None  # active | disabled


class ProgressRequest(BaseModel):
    chapter_index: int = 0


@protected_router.post("/share")
async def create_share(req: CreateShareRequest, user: AuthUser = Depends(require_auth)):
    novel = get_novel_by_id(req.novel_id)
    if novel is None:
        return JSONResponse(status_code=404, content={"ok": False, "error": "未找到该小说"})
    # Ownership: novels created with a known owner can only be shared by them
    # (or admin). Empty owner_id = legacy/CLI single-instance trust model.
    if novel.owner_id and novel.owner_id != (user.sub or "") and not user.is_admin:
        return JSONResponse(status_code=403, content={"ok": False, "error": "无权分享他人的小说"})

    book = await load_book_by_id(req.novel_id)
    if not book.chapters:
        return JSONResponse(status_code=409, content={"ok": False, "error": "小说还没有任何章节，无法分享"})

    mode, value = _validate_trial(req.trial_mode, req.trial_value)
    owner = user.sub or "anonymous"

    conn = await get_connection(settings.db_path)
    try:
        # 同一作者对同一小说只保留一个生效中分享（幂等）
        cursor = await conn.execute(
            "SELECT * FROM share_links WHERE novel_id = ? AND owner_id = ? AND status = 'active'",
            (req.novel_id, owner),
        )
        existing = await cursor.fetchone()
        if existing:
            return {"ok": True, "id": existing["id"], "share_url": f"/read/{existing['id']}", "created": False}

        # ID collisions are astronomically unlikely (48-bit random); the only
        # other IntegrityError is the partial unique index on concurrent
        # duplicate creates — return the winner instead of failing.
        sid = ""
        for _ in range(5):
            sid = secrets.token_urlsafe(_SHARE_ID_BYTES)
            try:
                await conn.execute(
                    """INSERT INTO share_links
                       (id, novel_id, owner_id, title_snapshot, intro_snapshot, genre_snapshot,
                        trial_mode, trial_value, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (sid, req.novel_id, owner, book.title, book.intro, book.genre, mode, value),
                )
                await conn.commit()
                break
            except sqlite3.IntegrityError:
                await conn.rollback()
                cursor = await conn.execute(
                    "SELECT * FROM share_links WHERE novel_id = ? AND owner_id = ? AND status = 'active'",
                    (req.novel_id, owner),
                )
                winner = await cursor.fetchone()
                if winner and winner["id"] != sid:
                    return {"ok": True, "id": winner["id"],
                            "share_url": f"/read/{winner['id']}", "created": False}
        else:  # pragma: no cover
            return JSONResponse(status_code=500, content={"ok": False, "error": "生成分享ID失败，请重试"})
    finally:
        await conn.close()

    return {"ok": True, "id": sid, "share_url": f"/read/{sid}", "created": True}


@protected_router.get("/shares")
async def list_my_shares(user: AuthUser = Depends(require_auth)):
    """我的分享列表（含统计与小说名）。"""
    conn = await get_connection(settings.db_path)
    try:
        cursor = await conn.execute(
            "SELECT * FROM share_links WHERE owner_id = ? ORDER BY created_at DESC",
            (user.sub or "anonymous",),
        )
        rows = await cursor.fetchall()
    finally:
        await conn.close()
    return {"shares": [dict(r) for r in rows]}


@protected_router.patch("/share/{share_id}")
async def update_share(share_id: str, req: PatchShareRequest, user: AuthUser = Depends(require_auth)):
    conn = await get_connection(settings.db_path)
    try:
        cursor = await conn.execute("SELECT * FROM share_links WHERE id = ?", (share_id,))
        row = await cursor.fetchone()
        if row is None:
            return JSONResponse(status_code=404, content={"ok": False, "error": "分享不存在"})
        if not user.is_admin and row["owner_id"] != (user.sub or "anonymous"):
            return JSONResponse(status_code=403, content={"ok": False, "error": "无权管理他人的分享"})

        mode, value = row["trial_mode"], row["trial_value"]
        if req.trial_mode is not None or req.trial_value is not None:
            mode, value = _validate_trial(
                req.trial_mode or row["trial_mode"],
                req.trial_value if req.trial_value is not None else row["trial_value"],
            )

        status = row["status"]
        if req.status is not None:
            if req.status not in ("active", "disabled"):
                return JSONResponse(status_code=400, content={"ok": False, "error": "非法状态"})
            status = req.status

        await conn.execute(
            """UPDATE share_links SET trial_mode = ?, trial_value = ?, status = ?,
                   disabled_at = CASE WHEN ? = 'disabled' THEN CURRENT_TIMESTAMP ELSE NULL END
               WHERE id = ?""",
            (mode, value, status, status, share_id),
        )
        await conn.commit()
    finally:
        await conn.close()
    return {"ok": True, "id": share_id, "trial_mode": mode, "trial_value": value, "status": status}


# ── 公开：阅读 ────────────────────────────────────────────────────────────

@router.get("/share/{share_id}")
async def public_share_meta(share_id: str, user: AuthUser | None = Depends(optional_auth_header)):
    conn = await get_connection(settings.db_path)
    try:
        row = await _fetch_share(conn, share_id)
        if row is None:
            return JSONResponse(status_code=404, content={"detail": "分享不存在或已关闭"})
        book = await load_book_by_id(row["novel_id"])
        if book is None:
            return JSONResponse(status_code=404, content={"detail": "分享不存在或已关闭"})
        cursor = await conn.execute(
            "UPDATE share_links SET view_count = view_count + 1 WHERE id = ? RETURNING view_count",
            (share_id,),
        )
        updated = await cursor.fetchone()
        await conn.commit()
        meta = _share_meta(row, authed=user is not None, total_chapters=len(book.chapters))
        if updated:
            meta["stats"]["views"] = updated["view_count"]
        return meta
    finally:
        await conn.close()


def _toc(book: Book, row, authed: bool) -> list[dict]:
    cum = 0
    items = []
    total_words = book.total_words
    for ch in book.chapters:
        readable = chapter_readable(
            ch.index, len(book.chapters), total_words, cum,
            row["trial_mode"], row["trial_value"], authed,
        )
        items.append({
            "index": ch.index,
            "title": ch.title or f"第{ch.index + 1}章",
            "words": ch.words,
            "readable": readable,
        })
        cum += ch.words
    return items


@router.get("/share/{share_id}/chapters")
async def public_share_chapters(share_id: str, user: AuthUser | None = Depends(optional_auth_header)):
    conn = await get_connection(settings.db_path)
    try:
        row = await _fetch_share(conn, share_id)
        if row is None:
            return JSONResponse(status_code=404, content={"detail": "分享不存在或已关闭"})
        book = await load_book_by_id(row["novel_id"])
        if book is None:
            return JSONResponse(status_code=404, content={"detail": "分享不存在或已关闭"})
        return {
            "id": share_id,
            "title": row["title_snapshot"],
            "authed": user is not None,
            "chapters": _toc(book, row, user is not None),
        }
    finally:
        await conn.close()


@router.get("/share/{share_id}/chapter/{chapter_index}")
async def public_share_chapter(
    share_id: str, chapter_index: int, user: AuthUser | None = Depends(optional_auth_header)
):
    conn = await get_connection(settings.db_path)
    try:
        row = await _fetch_share(conn, share_id)
        if row is None:
            return JSONResponse(status_code=404, content={"detail": "分享不存在或已关闭"})
        book = await load_book_by_id(row["novel_id"])
        if book is None:
            return JSONResponse(status_code=404, content={"detail": "分享不存在或已关闭"})

        authed = user is not None
        cum = 0
        target = None
        for ch in book.chapters:
            if ch.index == chapter_index:
                target = ch
                target_cum = cum
                break
            cum += ch.words
        if target is None:
            return JSONResponse(status_code=404, content={"detail": "章节不存在"})

        if not chapter_readable(
            target.index, len(book.chapters), book.total_words, target_cum,
            row["trial_mode"], row["trial_value"], authed,
        ):
            # 越权响应约定：绝不下发正文
            return JSONResponse(
                status_code=403,
                content={
                    "code": "need_login",
                    "message": "该章节超出试读范围，注册后即可阅读全部章节",
                    "trial_ok": False,
                },
            )

        await conn.execute(
            "UPDATE share_links SET read_count = read_count + 1 WHERE id = ?", (share_id,)
        )
        await conn.commit()

        # 登录读者自动记录阅读进度（书架）
        progress_saved = False
        if authed:
            await conn.execute(
                """INSERT INTO read_progress (user_code, share_id, novel_id, chapter_index, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(user_code, share_id) DO UPDATE SET
                       chapter_index = excluded.chapter_index,
                       updated_at = CURRENT_TIMESTAMP""",
                (user.sub, share_id, row["novel_id"], target.index),
            )
            await conn.commit()
            progress_saved = True

        next_index = target.index + 1
        next_exists = any(c.index == next_index for c in book.chapters)
        next_readable = True
        if next_exists and not authed:
            next_cum = target_cum + target.words
            next_readable = chapter_readable(
                next_index, len(book.chapters), book.total_words, next_cum,
                row["trial_mode"], row["trial_value"], False,
            )

        return {
            "index": target.index,
            "title": target.title or f"第{target.index + 1}章",
            "content": target.text,
            "words": target.words,
            "has_prev": target.index > 0,
            "has_next": next_exists,
            "next_readable": next_readable if next_exists else None,
            "authed": authed,
            "progress_saved": progress_saved,
        }
    finally:
        await conn.close()


# ── 注册读者：书架 / 进度 ─────────────────────────────────────────────────

@protected_router.post("/share/{share_id}/progress")
async def save_progress(
    share_id: str, req: ProgressRequest, user: AuthUser = Depends(require_auth)
):
    conn = await get_connection(settings.db_path)
    try:
        row = await _fetch_share(conn, share_id)
        if row is None:
            return JSONResponse(status_code=404, content={"ok": False, "error": "分享不存在或已关闭"})
        book = await load_book_by_id(row["novel_id"])
        max_index = max((c.index for c in book.chapters), default=0) if book else 0
        index = max(0, min(req.chapter_index, max_index))
        await conn.execute(
            """INSERT INTO read_progress (user_code, share_id, novel_id, chapter_index, updated_at)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_code, share_id) DO UPDATE SET
                   chapter_index = excluded.chapter_index,
                   updated_at = CURRENT_TIMESTAMP""",
            (user.sub, share_id, row["novel_id"], index),
        )
        await conn.commit()
    finally:
        await conn.close()
    return {"ok": True}


@protected_router.get("/bookshelf")
async def my_bookshelf(user: AuthUser = Depends(require_auth)):
    """书架：进度 + 分享快照（分享被关闭仍保留记录，但标注不可读）。"""
    conn = await get_connection(settings.db_path)
    try:
        cursor = await conn.execute(
            """SELECT rp.share_id, rp.chapter_index, rp.updated_at,
                      sl.title_snapshot, sl.genre_snapshot, sl.status AS share_status
               FROM read_progress rp
               LEFT JOIN share_links sl ON sl.id = rp.share_id
               WHERE rp.user_code = ?
               ORDER BY rp.updated_at DESC""",
            (user.sub,),
        )
        rows = await cursor.fetchall()
    finally:
        await conn.close()
    return {
        "books": [
            {
                "share_id": r["share_id"],
                "title": r["title_snapshot"] or "（已删除的分享）",
                "genre": r["genre_snapshot"],
                "chapter_index": r["chapter_index"],
                "updated_at": r["updated_at"],
                "available": r["share_status"] == "active",
            }
            for r in rows
        ]
    }
