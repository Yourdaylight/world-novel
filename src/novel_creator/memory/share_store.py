"""Share links & reader bookshelf data access (Milestone 15, Requirement B).

Tables live in the **central** database (``settings.db_path``) — the same DB
that holds ``invite_codes`` / ``user_quotas`` — while chapter content stays in
each novel's own SQLite file.

Design constraints (needs doc §4.6):
- share id is an unguessable random short code (>= 8 chars)
- disabled shares behave as if they never existed (404 everywhere)
- full-text gate is ``require_auth`` at the route layer ("注册即全文")
"""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

# Unambiguous alphabet (no O/0/I/l) — same convention as invite codes
_SHARE_ID_ALPHABET = (string.ascii_letters + string.digits).translate(
    str.maketrans("", "", "O0Il")
)
_SHARE_ID_LENGTH = 10  # spec: >= 8

TRIAL_MODE_FIRST_N = "first_n_chapters"
TRIAL_MODE_WORD_COUNT = "word_count"
TRIAL_MODE_RATIO = "ratio"
VALID_TRIAL_MODES = (TRIAL_MODE_FIRST_N, TRIAL_MODE_WORD_COUNT, TRIAL_MODE_RATIO)


def generate_share_id() -> str:
    """Generate an unguessable share short code (10 chars, unambiguous alphabet)."""
    return "".join(secrets.choice(_SHARE_ID_ALPHABET) for _ in range(_SHARE_ID_LENGTH))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ══════════════════════════════════════════════════════════════
# share_links CRUD
# ══════════════════════════════════════════════════════════════


async def create_share(
    conn: aiosqlite.Connection,
    *,
    novel_id: str,
    owner_id: str,
    title: str = "",
    cover: str = "",
    intro: str = "",
    trial_mode: str = TRIAL_MODE_FIRST_N,
    trial_value: int = 3,
) -> dict:
    """Create a new share link. One active share per novel — reactivates/updates
    the existing one instead of creating duplicates."""
    if trial_mode not in VALID_TRIAL_MODES:
        raise ValueError(f"invalid trial_mode: {trial_mode}")

    # Reuse an existing share for this novel (single canonical link per book)
    async with conn.execute(
        "SELECT id FROM share_links WHERE novel_id = ?", (novel_id,)
    ) as cursor:
        row = await cursor.fetchone()
    if row is not None:
        share_id = row["id"]
        await conn.execute(
            """UPDATE share_links
               SET status = 'active', disabled_at = NULL,
                   title_snapshot = ?, cover_snapshot = ?, intro_snapshot = ?,
                   trial_mode = ?, trial_value = ?
               WHERE id = ?""",
            (title, cover, intro, trial_mode, trial_value, share_id),
        )
        await conn.commit()
        return await get_share(conn, share_id)  # type: ignore[return-value]

    share_id = generate_share_id()
    await conn.execute(
        """INSERT INTO share_links
           (id, novel_id, owner_id, title_snapshot, cover_snapshot,
            intro_snapshot, trial_mode, trial_value, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
        (share_id, novel_id, owner_id, title, cover, intro,
         trial_mode, trial_value, _now()),
    )
    await conn.commit()
    return await get_share(conn, share_id)  # type: ignore[return-value]


async def get_share(conn: aiosqlite.Connection, share_id: str) -> Optional[dict]:
    async with conn.execute(
        "SELECT * FROM share_links WHERE id = ?", (share_id,)
    ) as cursor:
        row = await cursor.fetchone()
    return dict(row) if row else None


async def get_active_share(conn: aiosqlite.Connection, share_id: str) -> Optional[dict]:
    """Only active shares are visible; disabled ones behave as 404."""
    async with conn.execute(
        "SELECT * FROM share_links WHERE id = ? AND status = 'active'",
        (share_id,),
    ) as cursor:
        row = await cursor.fetchone()
    return dict(row) if row else None


async def get_share_by_novel(conn: aiosqlite.Connection, novel_id: str) -> Optional[dict]:
    async with conn.execute(
        "SELECT * FROM share_links WHERE novel_id = ? ORDER BY created_at DESC LIMIT 1",
        (novel_id,),
    ) as cursor:
        row = await cursor.fetchone()
    return dict(row) if row else None


async def list_shares_for_owner(
    conn: aiosqlite.Connection, owner_id: str
) -> list[dict]:
    async with conn.execute(
        "SELECT * FROM share_links WHERE owner_id = ? ORDER BY created_at DESC",
        (owner_id,),
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def update_share(
    conn: aiosqlite.Connection,
    share_id: str,
    *,
    trial_mode: Optional[str] = None,
    trial_value: Optional[int] = None,
    title: Optional[str] = None,
    intro: Optional[str] = None,
) -> bool:
    """Update mutable share fields. Trial changes take effect immediately."""
    fields: list[str] = []
    values: list = []
    if trial_mode is not None:
        if trial_mode not in VALID_TRIAL_MODES:
            raise ValueError(f"invalid trial_mode: {trial_mode}")
        fields.append("trial_mode = ?")
        values.append(trial_mode)
    if trial_value is not None:
        fields.append("trial_value = ?")
        values.append(trial_value)
    if title is not None:
        fields.append("title_snapshot = ?")
        values.append(title)
    if intro is not None:
        fields.append("intro_snapshot = ?")
        values.append(intro)
    if not fields:
        return False
    values.append(share_id)
    await conn.execute(
        f"UPDATE share_links SET {', '.join(fields)} WHERE id = ?", values
    )
    await conn.commit()
    return True


async def set_share_status(
    conn: aiosqlite.Connection, share_id: str, status: str
) -> bool:
    """Enable/disable a share. Disabling stamps disabled_at."""
    if status not in ("active", "disabled"):
        raise ValueError(f"invalid status: {status}")
    disabled_at = None if status == "active" else _now()
    await conn.execute(
        "UPDATE share_links SET status = ?, disabled_at = ? WHERE id = ?",
        (status, disabled_at, share_id),
    )
    await conn.commit()
    return True


async def bump_share_counter(
    conn: aiosqlite.Connection, share_id: str, column: str
) -> None:
    """Increment view_count / read_count / register_count atomically."""
    if column not in ("view_count", "read_count", "register_count"):
        raise ValueError(f"invalid counter column: {column}")
    await conn.execute(
        f"UPDATE share_links SET {column} = {column} + 1 WHERE id = ?",
        (share_id,),
    )
    await conn.commit()


# ══════════════════════════════════════════════════════════════
# Daily stats (PV / reads / UV)
# ══════════════════════════════════════════════════════════════


async def record_daily_stat(
    conn: aiosqlite.Connection,
    share_id: str,
    *,
    views: int = 0,
    reads: int = 0,
    new_visitor: bool = False,
) -> None:
    """Upsert today's counters for a share."""
    today = _today()
    await conn.execute(
        """INSERT INTO share_stats (share_id, stat_date, views, reads, visitors)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(share_id, stat_date) DO UPDATE SET
             views = views + excluded.views,
             reads = reads + excluded.reads,
             visitors = visitors + excluded.visitors""",
        (share_id, today, views, reads, 1 if new_visitor else 0),
    )
    await conn.commit()


async def get_share_stats(
    conn: aiosqlite.Connection, share_id: str, days: int = 30
) -> list[dict]:
    async with conn.execute(
        """SELECT stat_date, views, reads, visitors FROM share_stats
           WHERE share_id = ? ORDER BY stat_date DESC LIMIT ?""",
        (share_id, days),
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def record_conversion(
    conn: aiosqlite.Connection, share_id: str, user_code: str
) -> bool:
    """Record a trial→registered conversion. Idempotent per (share, user).
    Returns True if this call recorded a new conversion."""
    try:
        await conn.execute(
            "INSERT INTO share_conversions (share_id, user_code, created_at) "
            "VALUES (?, ?, ?)",
            (share_id, user_code, _now()),
        )
        await conn.execute(
            "UPDATE share_links SET register_count = register_count + 1 "
            "WHERE id = ?",
            (share_id,),
        )
        await conn.commit()
        return True
    except aiosqlite.IntegrityError:
        return False  # already converted


# ══════════════════════════════════════════════════════════════
# Bookshelf & reading progress
# ══════════════════════════════════════════════════════════════


async def upsert_progress(
    conn: aiosqlite.Connection,
    *,
    user_code: str,
    novel_id: str,
    chapter_index: int,
    share_id: str = "",
) -> None:
    await conn.execute(
        """INSERT INTO read_progress
           (user_code, novel_id, share_id, chapter_index, in_bookshelf, last_read_at)
           VALUES (?, ?, ?, ?, 0, ?)
           ON CONFLICT(user_code, novel_id) DO UPDATE SET
             chapter_index = excluded.chapter_index,
             share_id = CASE WHEN excluded.share_id != ''
                             THEN excluded.share_id ELSE read_progress.share_id END,
             last_read_at = excluded.last_read_at""",
        (user_code, novel_id, share_id, chapter_index, _now()),
    )
    await conn.commit()


async def get_progress(
    conn: aiosqlite.Connection, user_code: str, novel_id: str
) -> Optional[dict]:
    async with conn.execute(
        "SELECT * FROM read_progress WHERE user_code = ? AND novel_id = ?",
        (user_code, novel_id),
    ) as cursor:
        row = await cursor.fetchone()
    return dict(row) if row else None


async def set_bookshelf(
    conn: aiosqlite.Connection,
    *,
    user_code: str,
    novel_id: str,
    in_bookshelf: bool,
    share_id: str = "",
) -> None:
    await conn.execute(
        """INSERT INTO read_progress
           (user_code, novel_id, share_id, chapter_index, in_bookshelf, last_read_at)
           VALUES (?, ?, ?, 0, ?, ?)
           ON CONFLICT(user_code, novel_id) DO UPDATE SET
             in_bookshelf = excluded.in_bookshelf,
             share_id = CASE WHEN excluded.share_id != ''
                             THEN excluded.share_id ELSE read_progress.share_id END""",
        (user_code, novel_id, share_id, 1 if in_bookshelf else 0, _now()),
    )
    await conn.commit()


async def list_bookshelf(
    conn: aiosqlite.Connection, user_code: str
) -> list[dict]:
    async with conn.execute(
        """SELECT * FROM read_progress
           WHERE user_code = ? AND in_bookshelf = 1
           ORDER BY last_read_at DESC""",
        (user_code,),
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]
