"""publication_records store — every export / publish attempt is auditable."""

from __future__ import annotations

import json
import secrets

from novel_creator.memory.database import get_connection
from novel_creator.config import settings


def _new_id() -> str:
    return "pub_" + secrets.token_urlsafe(8)


async def create_record(
    *,
    novel_id: str,
    platform: str,
    operator: str,
    export_meta: dict,
    stage: str = "exported",
) -> dict:
    record_id = _new_id()
    conn = await get_connection(settings.db_path)
    try:
        await conn.execute(
            """INSERT INTO publication_records
               (id, novel_id, platform, stage, export_meta, operator)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (record_id, novel_id, platform, stage, json.dumps(export_meta, ensure_ascii=False), operator),
        )
        await conn.commit()
    finally:
        await conn.close()
    return await get_record(record_id) or {"id": record_id}


async def get_record(record_id: str) -> dict | None:
    conn = await get_connection(settings.db_path)
    try:
        cursor = await conn.execute(
            "SELECT * FROM publication_records WHERE id = ?", (record_id,)
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None
    finally:
        await conn.close()


async def list_records(novel_id: str | None = None) -> list[dict]:
    conn = await get_connection(settings.db_path)
    try:
        if novel_id:
            cursor = await conn.execute(
                "SELECT * FROM publication_records WHERE novel_id = ? "
                "ORDER BY created_at DESC",
                (novel_id,),
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM publication_records ORDER BY created_at DESC"
            )
        rows = await cursor.fetchall()
        return [d for d in (_row_to_dict(r) for r in rows) if d]
    finally:
        await conn.close()


async def update_record(
    record_id: str,
    *,
    target_book_id: str | None = None,
    target_url: str | None = None,
    stage: str | None = None,
) -> dict | None:
    """Backfill platform-side book ID / URL after manual upload (A-5)."""
    fields: list[str] = []
    values: list = []
    if target_book_id is not None:
        fields.append("target_book_id = ?")
        values.append(target_book_id)
    if target_url is not None:
        fields.append("target_url = ?")
        values.append(target_url)
    if stage is not None:
        fields.append("stage = ?")
        values.append(stage)
    if not fields:
        return await get_record(record_id)
    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(record_id)

    conn = await get_connection(settings.db_path)
    try:
        await conn.execute(
            f"UPDATE publication_records SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        await conn.commit()
    finally:
        await conn.close()
    return await get_record(record_id)


def _row_to_dict(row) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    try:
        data["export_meta"] = json.loads(data.get("export_meta") or "{}")
    except (TypeError, json.JSONDecodeError):
        data["export_meta"] = {}
    return data
