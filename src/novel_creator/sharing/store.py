"""share_links / read_progress store (global DB)."""

from __future__ import annotations

import secrets
from typing import Any

import aiosqlite


def new_share_id() -> str:
    """不可枚举随机短码：token_urlsafe(9) → 12 个 URL 安全字符（>=8 位要求）。"""
    return secrets.token_urlsafe(9)


def row_to_dict(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


async def create_share(
    conn: aiosqlite.Connection,
    *,
    novel_id: str,
    owner_id: str,
    title: str,
    intro: str,
    genre: str = "",
    author: str = "",
    trial_mode: str = "first_n_chapters",
    trial_value: int = 3,
    chapter_count: int = 0,
    word_count: int = 0,
) -> dict:
    share_id = new_share_id()
    await conn.execute(
        """INSERT INTO share_links
           (id, novel_id, owner_id, title, author, intro, genre,
            trial_mode, trial_value, chapter_count, word_count)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            share_id, novel_id, owner_id, title, author, intro, genre,
            trial_mode, trial_value, chapter_count, word_count,
        ),
    )
    await conn.commit()
    row = await _get(conn, share_id)
    return row_to_dict(row)  # type: ignore[return-value]


async def _get(conn: aiosqlite.Connection, share_id: str) -> aiosqlite.Row | None:
    cursor = await conn.execute("SELECT * FROM share_links WHERE id = ?", (share_id,))
    return await cursor.fetchone()


async def get_active_share(
    conn: aiosqlite.Connection, share_id: str
) -> dict | None:
    """Public lookups only ever see active shares; disabled → 404 upstream."""
    cursor = await conn.execute(
        "SELECT * FROM share_links WHERE id = ? AND status = 'active'",
        (share_id,),
    )
    return row_to_dict(await cursor.fetchone())


async def get_share_any(
    conn: aiosqlite.Connection, share_id: str
) -> dict | None:
    return row_to_dict(await _get(conn, share_id))


async def list_owner_shares(
    conn: aiosqlite.Connection, owner_id: str
) -> list[dict]:
    cursor = await conn.execute(
        "SELECT * FROM share_links WHERE owner_id = ? ORDER BY created_at DESC",
        (owner_id,),
    )
    return [dict(r) for r in await cursor.fetchall()]


async def update_share_settings(
    conn: aiosqlite.Connection,
    share_id: str,
    owner_id: str,
    *,
    trial_mode: str | None = None,
    trial_value: int | None = None,
    status: str | None = None,
    is_admin: bool = False,
) -> dict | None:
    """Owner-only update; admins may manage any share. Returns None if denied/missing."""
    share = row_to_dict(await _get(conn, share_id))
    if share is None:
        return None
    if not is_admin and share["owner_id"] != owner_id:
        return None

    fields: list[str] = []
    values: list[Any] = []
    if trial_mode is not None:
        fields.append("trial_mode = ?")
        values.append(trial_mode)
    if trial_value is not None:
        fields.append("trial_value = ?")
        values.append(trial_value)
    if status is not None:
        fields.append("status = ?")
        values.append(status)
        if status == "disabled":
            fields.append("disabled_at = CURRENT_TIMESTAMP")
        elif status == "active":
            fields.append("disabled_at = NULL")
    if not fields:
        return share

    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(share_id)
    await conn.execute(
        f"UPDATE share_links SET {', '.join(fields)} WHERE id = ?", values
    )
    await conn.commit()
    return row_to_dict(await _get(conn, share_id))


async def increment_view(conn: aiosqlite.Connection, share_id: str) -> None:
    await conn.execute(
        "UPDATE share_links SET view_count = view_count + 1 WHERE id = ?",
        (share_id,),
    )
    await conn.commit()


async def increment_read(conn: aiosqlite.Connection, share_id: str) -> None:
    await conn.execute(
        "UPDATE share_links SET read_count = read_count + 1 WHERE id = ?",
        (share_id,),
    )
    await conn.commit()


# ── 书架 / 进度 ──────────────────────────────────────────────────────────

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
           VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(user_code, share_id) DO UPDATE SET
               chapter_index = excluded.chapter_index,
               last_read_at = CURRENT_TIMESTAMP""",
        (user_code, share_id, novel_id, chapter_index),
    )
    await conn.commit()


async def list_bookshelf(conn: aiosqlite.Connection, user_code: str) -> list[dict]:
    """Progress rows joined with share snapshots (only active shares)."""
    cursor = await conn.execute(
        """SELECT p.share_id, p.novel_id, p.chapter_index, p.last_read_at,
                  s.title, s.author, s.intro, s.genre, s.cover,
                  s.chapter_count, s.word_count, s.status
           FROM read_progress p
           JOIN share_links s ON s.id = p.share_id
           WHERE p.user_code = ? AND s.status = 'active'
           ORDER BY p.last_read_at DESC""",
        (user_code,),
    )
    return [dict(r) for r in await cursor.fetchall()]
