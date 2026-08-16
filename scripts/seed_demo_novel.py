#!/usr/bin/env python3
"""Seed a demo 10-chapter novel + invite codes for local E2E verification.

Run from the repo root with the server's data directory as CWD:
    uv run python scripts/seed_demo_novel.py

Creates:
  - data/registry.json + data/novels/demo-jianghu/novel.db (10 chapters, 1 volume)
  - invite codes: admin001 (admin) / reader001 / reader002 (in data/novel.db)
"""

from __future__ import annotations

import asyncio
import json

from novel_creator.config import settings
from novel_creator.memory import registry as registry_mod
from novel_creator.memory.database import get_connection

NOVEL_ID = "demo-jianghu"
TITLE = "江湖拾遗录"


async def main() -> None:
    # ── Novel DB ──────────────────────────────────────────────
    info = registry_mod.register_novel(TITLE, "武侠", num_chapters=10)
    conn = await get_connection(info.db_path)
    outline = {
        "title": TITLE,
        "genre": "武侠",
        "synopsis": "少年沈拾遗踏入江湖，卷入一场跨越二十年的恩怨。刀光剑影之间，他逐渐发现自己的身世与整个武林的秘密相连。",
        "premise": "一个普通少年在江湖中成长为一代宗师。",
        "chapters": [{"index": i, "title": f"第{i + 1}章"} for i in range(10)],
    }
    await conn.execute(
        "INSERT INTO story_outline (id, outline_json) VALUES (1, ?)",
        (json.dumps(outline, ensure_ascii=False),),
    )
    await conn.execute(
        "INSERT INTO volumes (volume_index, title, summary, chapter_start, chapter_end) "
        "VALUES (0, '初入江湖', '少年下山', 0, 9)"
    )
    for i in range(10):
        paragraphs = [
            f"第{i + 1}章的故事就此展开。沈拾遗走在青石板路上，"
            f"心中默念师父的教诲。风从远处吹来，带着酒香与血腥气。",
            "他知道，自己已经没有退路。这一局棋，从二十年前便已布下。",
            f"这一日发生的事情，后来被写进了《江湖拾遗录》的第{i + 1}个卷轴。",
        ]
        await conn.execute(
            "INSERT INTO chapter_texts (chapter_index, scene_index, title, content) "
            "VALUES (?, 0, ?, ?)",
            (i, f"风云第{i + 1}变", "\n\n".join(paragraphs)),
        )
    await conn.commit()
    await conn.close()
    registry_mod.update_novel_status(
        info.novel_id, status="completed", chapters_completed=10, word_count=12000
    )

    # ── Global DB: invite codes ───────────────────────────────
    conn = await get_connection(settings.db_path)
    for code in ("admin001", "reader001", "reader002"):
        await conn.execute(
            "INSERT OR IGNORE INTO invite_codes (code, is_active, max_uses, description) "
            "VALUES (?, 1, 0, 'demo')",
            (code,),
        )
    await conn.commit()
    await conn.close()

    print(f"✓ novel seeded: {info.novel_id} ({info.db_path})")
    print("✓ invite codes: admin001 / reader001 / reader002")


if __name__ == "__main__":
    asyncio.run(main())
