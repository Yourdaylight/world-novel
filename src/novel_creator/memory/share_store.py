"""Share-link & reading-progress store (central db — settings.db_path).

Requirement B. A share link is an *ungessable* public handle to one novel; its
row snapshots the title/intro shown on the reader page. Anonymous readers get
only the configured trial window; any authenticated user reads the full book
(open-source "register = full access"; paid membership is reserved for the
commercial edition and intentionally not modelled here).
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

import sqlite3

import aiosqlite

# 10 chars from a 56-symbol ambiguous-free alphabet ≈ 58 bits — not enumerable.
_SHARE_ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_SHARE_LEN = 10


def new_share_id() -> str:
    return "".join(secrets.choice(_SHARE_ALPHABET) for _ in range(_SHARE_LEN))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_share(row: aiosqlite.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    try:
        d["meta"] = json.loads(d.pop("meta_json") or "{}")
    except (ValueError, TypeError):
        d["meta"] = {}
    return d


async def create_share(
    conn: aiosqlite.Connection,
    *,
    novel_id: str,
    owner_id: str,
    title: str,
    intro: str,
    cover: str = "",
    meta: dict | None = None,
    trial_mode: str = "first_n_chapters",
    trial_value: int = 3,
) -> dict:
    # Retry on the astronomically unlikely chance of an id collision.
    for _ in range(5):
        share_id = new_share_id()
        now = _now()
        try:
            await conn.execute(
                """INSERT INTO share_links
                   (id, novel_id, owner_id, title, intro, cover, meta_json,
                    trial_mode, trial_value, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
                (
                    share_id, novel_id, owner_id, title, intro, cover,
                    json.dumps(meta or {}, ensure_ascii=False),
                    trial_mode, trial_value, now, now,
                ),
            )
            await conn.commit()
            break
        except sqlite3.IntegrityError:
            # primary-key collision — regenerate
            share_id = ""  # type: ignore[assignment]
    if not share_id:
        raise RuntimeError("无法生成唯一分享 ID")
    share = await get_share(conn, share_id)
    return share  # type: ignore[return-value]


async def get_share(
    conn: aiosqlite.Connection, share_id: str, *, only_active: bool = False
) -> dict | None:
    sql = "SELECT * FROM share_links WHERE id = ?"
    if only_active:
        sql += " AND status = 'active'"
    async with conn.execute(sql, (share_id,)) as cursor:
        return _row_to_share(await cursor.fetchone())


async def list_shares_by_owner(conn: aiosqlite.Connection, owner_id: str) -> list[dict]:
    async with conn.execute(
        "SELECT * FROM share_links WHERE owner_id = ? ORDER BY created_at DESC",
        (owner_id,),
    ) as cursor:
        return [d for d in (_row_to_share(r) for r in await cursor.fetchall()) if d]


async def list_active_share_for_novel(
    conn: aiosqlite.Connection, novel_id: str, owner_id: str | None = None
) -> dict | None:
    """Return the author's active share for a novel (at most one per novel/owner)."""
    if owner_id:
        sql = ("SELECT * FROM share_links WHERE novel_id = ? AND owner_id = ? "
               "AND status = 'active' ORDER BY created_at DESC LIMIT 1")
        params: tuple = (novel_id, owner_id)
    else:
        sql = ("SELECT * FROM share_links WHERE novel_id = ? AND status = 'active' "
               "ORDER BY created_at DESC LIMIT 1")
        params = (novel_id,)
    async with conn.execute(sql, params) as cursor:
        return _row_to_share(await cursor.fetchone())


async def update_share(
    conn: aiosqlite.Connection,
    share_id: str,
    *,
    trial_mode: str | None = None,
    trial_value: int | None = None,
    status: str | None = None,
    title: str | None = None,
    intro: str | None = None,
) -> bool:
    fields: list[str] = []
    params: list = []
    for col, val in (
        ("trial_mode", trial_mode),
        ("trial_value", trial_value),
        ("status", status),
        ("title", title),
        ("intro", intro),
    ):
        if val is not None:
            fields.append(f"{col} = ?")
            params.append(val)
    if not fields:
        return False
    if status == "disabled":
        fields.append("disabled_at = ?")
        params.append(_now())
    elif status == "active":
        fields.append("disabled_at = NULL")
    fields.append("updated_at = ?")
    params.append(_now())
    params.append(share_id)
    cur = await conn.execute(
        f"UPDATE share_links SET {', '.join(fields)} WHERE id = ?", params
    )
    await conn.commit()
    return cur.rowcount > 0


async def increment_view(conn: aiosqlite.Connection, share_id: str) -> None:
    await conn.execute(
        "UPDATE share_links SET view_count = view_count + 1 WHERE id = ?", (share_id,)
    )
    await conn.commit()


async def increment_read(conn: aiosqlite.Connection, share_id: str) -> None:
    await conn.execute(
        "UPDATE share_links SET read_count = read_count + 1 WHERE id = ?", (share_id,)
    )
    await conn.commit()


# ── Bookshelf / reading progress (registered users) ────────────────────────

async def upsert_progress(
    conn: aiosqlite.Connection,
    *,
    user_code: str,
    share_id: str,
    novel_id: str,
    chapter_index: int,
) -> None:
    await conn.execute(
        """INSERT INTO read_progress (user_code, share_id, novel_id, chapter_index, last_read_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(user_code, share_id) DO UPDATE SET
               chapter_index = excluded.chapter_index,
               novel_id = excluded.novel_id,
               last_read_at = excluded.last_read_at""",
        (user_code, share_id, novel_id, chapter_index, _now()),
    )
    await conn.commit()


async def list_progress(conn: aiosqlite.Connection, user_code: str) -> list[dict]:
    async with conn.execute(
        """SELECT rp.share_id, rp.novel_id, rp.chapter_index, rp.last_read_at,
                  sl.title, sl.cover, sl.status
           FROM read_progress rp
           LEFT JOIN share_links sl ON sl.id = rp.share_id
           WHERE rp.user_code = ?
           ORDER BY rp.last_read_at DESC""",
        (user_code,),
    ) as cursor:
        return [dict(r) for r in await cursor.fetchall()]
