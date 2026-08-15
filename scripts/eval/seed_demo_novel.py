#!/usr/bin/env python3
"""Seed a demo novel + invite codes for Milestone 15 evaluation.

Works against a RUNNING server's database (reads NOVEL_DB_PATH from env or
data/novel.db default), so it can be used before/while the server runs.

Usage:
    uv run python scripts/eval/seed_demo_novel.py [--chapters 12]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from novel_creator.config import settings  # noqa: E402
from novel_creator.memory.database import get_connection  # noqa: E402
from novel_creator.memory.registry import get_novel_by_id, register_novel  # noqa: E402

TITLE = "星尘纪元"
GENRE = "科幻"
CODES = {
    "admin_demo": "管理员",
    "author_demo": "作者演示",
    "reader_demo": "读者演示",
}


async def seed(chapters: int) -> None:
    # invite codes (max_uses=0 → unlimited)
    conn = await get_connection(settings.db_path)
    for code, desc in CODES.items():
        await conn.execute(
            "INSERT OR IGNORE INTO invite_codes (code, description, is_active, max_uses) "
            "VALUES (?, ?, 1, 0)",
            (code, desc),
        )
    await conn.commit()
    await conn.close()

    # demo novel
    info = get_novel_by_id("星尘纪元") or register_novel(
        title=TITLE, genre=GENRE, num_chapters=chapters
    )
    conn = await get_connection(info.db_path)
    cursor = await conn.execute("SELECT COUNT(*) AS n FROM chapter_texts")
    row = await cursor.fetchone()
    if row["n"] > 0:
        print(f"demo novel '{info.novel_id}' already has content, skipping chapters")
        await conn.close()
        return

    body_tpl = (
        "星舰穿过陨石带的瞬间，林远看见了那颗蓝色星球的轮廓。"
        "三百年前的航迹图上，这里被标注为禁区。"
        "他握紧操纵杆，低声说：我们回家。"
    )
    for i in range(chapters):
        await conn.execute(
            "INSERT INTO chapter_texts (chapter_index, scene_index, title, content, summary) "
            "VALUES (?, 0, ?, ?, ?)",
            (i, f"归途{i + 1}", (body_tpl * 8) + f"\n\n（第{i + 1}章完）", f"第{i + 1}章概要"),
        )

    half = chapters // 2
    await conn.execute(
        "INSERT OR REPLACE INTO volumes (volume_index, title, chapter_start, chapter_end) "
        "VALUES (0, '第一卷 离港', 0, ?)",
        (half - 1,),
    )
    await conn.execute(
        "INSERT OR REPLACE INTO volumes (volume_index, title, chapter_start, chapter_end) "
        "VALUES (1, '第二卷 归途', ?, ?)",
        (half, chapters - 1),
    )
    outline = {
        "title": TITLE,
        "genre": GENRE,
        "theme": "归乡",
        "premise": "星际流浪三百年后，最后一艘殖民舰决定返回地球。",
        "setting": "公元25世纪，人类散布于银河十二个星系。",
        "chapters": [
            {"chapter_index": i, "title": f"归途{i + 1}"} for i in range(chapters)
        ],
        "volumes": [],
    }
    await conn.execute(
        "INSERT OR REPLACE INTO story_outline (id, outline_json) VALUES (1, ?)",
        (json.dumps(outline, ensure_ascii=False),),
    )
    await conn.commit()
    await conn.close()
    print(f"seeded novel '{info.novel_id}' ({chapters} chapters, 2 volumes)")
    print(f"invite codes: {', '.join(CODES)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chapters", type=int, default=12)
    args = parser.parse_args()
    asyncio.run(seed(args.chapters))
