"""Publication/export record store (central db — settings.db_path).

Records every L0 export and any later platform-side publish backfill, so the
author's console can show publication history (requirement A-3/A-5).
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

import aiosqlite


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_record_id() -> str:
    return "pub_" + secrets.token_urlsafe(8)


async def create_record(
    conn: aiosqlite.Connection,
    *,
    novel_id: str,
    platform: str,
    stage: str = "exported",
    export_meta: dict | None = None,
    operator: str = "",
) -> str:
    record_id = new_record_id()
    now = _now()
    await conn.execute(
        """INSERT INTO publication_records
           (id, novel_id, platform, stage, export_meta, operator, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            record_id,
            novel_id,
            platform,
            stage,
            json.dumps(export_meta or {}, ensure_ascii=False),
            operator,
            now,
            now,
        ),
    )
    await conn.commit()
    return record_id


async def list_records(
    conn: aiosqlite.Connection,
    *,
    novel_id: str | None = None,
    operator: str | None = None,
) -> list[dict]:
    sql = "SELECT * FROM publication_records WHERE 1=1"
    params: list = []
    if novel_id:
        sql += " AND novel_id = ?"
        params.append(novel_id)
    if operator:
        sql += " AND operator = ?"
        params.append(operator)
    sql += " ORDER BY created_at DESC LIMIT 200"
    async with conn.execute(sql, params) as cursor:
        rows = await cursor.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["export_meta"] = json.loads(d.get("export_meta") or "{}")
        except (ValueError, TypeError):
            d["export_meta"] = {}
        result.append(d)
    return result


async def update_publish_backfill(
    conn: aiosqlite.Connection,
    record_id: str,
    *,
    target_book_id: str = "",
    target_url: str = "",
    stage: str = "published",
) -> bool:
    """Mark a record as published on the platform side (A-5 backfill)."""
    cur = await conn.execute(
        """UPDATE publication_records
           SET target_book_id = ?, target_url = ?, stage = ?, updated_at = ?
           WHERE id = ?""",
        (target_book_id, target_url, stage, _now(), record_id),
    )
    await conn.commit()
    return cur.rowcount > 0
