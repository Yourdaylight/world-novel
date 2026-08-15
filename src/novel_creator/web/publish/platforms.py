"""Platform adaptation profiles (平台适配表, needs doc §3.4).

Seed rows are idempotently written to the central DB so new platforms can be
added later without a schema change. Reality check (needs doc §3.2): no Chinese
web-novel platform exposes a public open API — therefore L0 export is the
guaranteed path and these profiles describe *upload formats*, not API targets.
"""

from __future__ import annotations

import json
from typing import Optional

import aiosqlite

# platform → profile defaults
DEFAULT_PROFILES: list[dict] = [
    {
        "platform": "fanqie",
        "display_name": "番茄小说",
        "formats": "txt",
        "encoding": "gb18030",  # 番茄导入 TXT 推荐 GB18030/GBK 编码
        "chapter_max_words": 2000,  # 单章推荐 ≤2000 字
        "supports_volumes": 0,
        "cover_required": 1,
        "notes": "番茄作家助手网页/App 上传；无公开开放 API，导出后手动上传",
    },
    {
        "platform": "qimao",
        "display_name": "七猫小说",
        "formats": "txt",
        "encoding": "utf-8",
        "chapter_max_words": 0,
        "supports_volumes": 1,  # 支持分卷导入
        "cover_required": 1,
        "notes": "七猫作家平台网页上传；支持分卷，导出按卷拆分文件",
    },
    {
        "platform": "txt",
        "display_name": "通用 TXT",
        "formats": "txt",
        "encoding": "utf-8",
        "chapter_max_words": 0,
        "supports_volumes": 1,
        "cover_required": 0,
        "notes": "通用纯文本导出（UTF-8），适用任意平台手动粘贴",
    },
    {
        "platform": "epub",
        "display_name": "EPUB 电子书",
        "formats": "epub",
        "encoding": "utf-8",
        "chapter_max_words": 0,
        "supports_volumes": 1,
        "cover_required": 0,
        "notes": "标准 EPUB3 电子书，可直接导入阅读器或转格式上传",
    },
]


async def ensure_platform_profiles(conn: aiosqlite.Connection) -> None:
    """Idempotently seed default platform profiles."""
    for p in DEFAULT_PROFILES:
        await conn.execute(
            """INSERT OR IGNORE INTO platform_profiles
               (platform, display_name, formats, encoding, chapter_max_words,
                supports_volumes, cover_required, notes, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                p["platform"],
                p["display_name"],
                p["formats"],
                p["encoding"],
                p["chapter_max_words"],
                p["supports_volumes"],
                p["cover_required"],
                p["notes"],
            ),
        )
    await conn.commit()


async def get_platform_profile(
    conn: aiosqlite.Connection, platform: str
) -> Optional[dict]:
    await ensure_platform_profiles(conn)
    async with conn.execute(
        "SELECT * FROM platform_profiles WHERE platform = ? AND enabled = 1",
        (platform,),
    ) as cursor:
        row = await cursor.fetchone()
    return dict(row) if row else None


async def list_platform_profiles(conn: aiosqlite.Connection) -> list[dict]:
    await ensure_platform_profiles(conn)
    async with conn.execute(
        "SELECT * FROM platform_profiles WHERE enabled = 1 ORDER BY platform"
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════
# publication_records
# ══════════════════════════════════════════════════════════════

VALID_STAGES = (
    "draft",
    "exporting",
    "exported",
    "publishing",
    "published",
    "failed",
)


async def create_publication_record(
    conn: aiosqlite.Connection,
    *,
    record_id: str,
    novel_id: str,
    platform: str,
    operator: str,
    stage: str = "exporting",
    export_meta: dict | None = None,
) -> None:
    await conn.execute(
        """INSERT INTO publication_records
           (id, novel_id, platform, stage, export_meta, operator)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            record_id,
            novel_id,
            platform,
            stage,
            json.dumps(export_meta or {}, ensure_ascii=False),
            operator,
        ),
    )
    await conn.commit()


async def update_publication_record(
    conn: aiosqlite.Connection,
    record_id: str,
    *,
    stage: Optional[str] = None,
    target_book_id: Optional[str] = None,
    target_url: Optional[str] = None,
    export_meta: Optional[dict] = None,
) -> bool:
    fields: list[str] = ["updated_at = CURRENT_TIMESTAMP"]
    values: list = []
    if stage is not None:
        if stage not in VALID_STAGES:
            raise ValueError(f"invalid stage: {stage}")
        fields.append("stage = ?")
        values.append(stage)
    if target_book_id is not None:
        fields.append("target_book_id = ?")
        values.append(target_book_id)
    if target_url is not None:
        fields.append("target_url = ?")
        values.append(target_url)
    if export_meta is not None:
        fields.append("export_meta = ?")
        values.append(json.dumps(export_meta, ensure_ascii=False))
    values.append(record_id)
    await conn.execute(
        f"UPDATE publication_records SET {', '.join(fields)} WHERE id = ?",
        values,
    )
    await conn.commit()
    return True


async def get_publication_record(
    conn: aiosqlite.Connection, record_id: str
) -> Optional[dict]:
    async with conn.execute(
        "SELECT * FROM publication_records WHERE id = ?", (record_id,)
    ) as cursor:
        row = await cursor.fetchone()
    if row is None:
        return None
    rec = dict(row)
    rec["export_meta"] = json.loads(rec.get("export_meta") or "{}")
    return rec


async def list_publication_records(
    conn: aiosqlite.Connection, novel_id: Optional[str] = None
) -> list[dict]:
    if novel_id:
        sql = (
            "SELECT * FROM publication_records WHERE novel_id = ? "
            "ORDER BY created_at DESC"
        )
        params: tuple = (novel_id,)
    else:
        sql = "SELECT * FROM publication_records ORDER BY created_at DESC"
        params = ()
    async with conn.execute(sql, params) as cursor:
        rows = await cursor.fetchall()
    out = []
    for r in rows:
        rec = dict(r)
        rec["export_meta"] = json.loads(rec.get("export_meta") or "{}")
        out.append(rec)
    return out
