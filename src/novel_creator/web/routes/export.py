"""Export routes: /worlds/{id}/export/markdown, /worlds/{id}/export/json, /worlds/{id}/files, /worlds/{id}/files/download, /novel-full, /chapter-text/{idx}."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse, FileResponse

from novel_creator.memory.database import get_connection
from novel_creator.memory.registry import get_novel_by_id

from ._helpers import _get_novel_db

router = APIRouter()


@router.get("/chapter-text/{chapter_index}")
async def get_chapter_text(chapter_index: int, novel_id: str | None = Query(None)):
    """Get the rendered literary text for a specific chapter."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        cursor = await conn.execute(
            """SELECT * FROM chapter_texts
               WHERE chapter_index = ?
               ORDER BY scene_index""",
            (chapter_index,),
        )
        rows = await cursor.fetchall()
        await conn.close()
        if not rows:
            return {"title": "", "scenes": [], "full_text": "", "summary": ""}

        title = rows[0]["title"]
        summary = rows[0]["summary"] or ""
        scenes = [
            {
                "scene_index": r["scene_index"],
                "content": r["content"],
                "pov_character": r["pov_character"],
            }
            for r in rows
        ]
        full_text = "\n\n".join(r["content"] for r in rows)
        return {"title": title, "scenes": scenes, "full_text": full_text, "summary": summary}
    except Exception as e:
        return {"error": str(e), "title": "", "scenes": [], "full_text": "", "summary": ""}


@router.get("/novel-full")
async def get_novel_full(novel_id: str | None = Query(None)):
    """Get the full compiled novel text — all chapters joined."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        # Get outline for title
        cursor0 = await conn.execute("SELECT outline_json FROM story_outline WHERE id = 1")
        row0 = await cursor0.fetchone()
        outline = json.loads(row0["outline_json"]) if row0 else {}
        title = outline.get("title", "未命名小说")
        genre = outline.get("genre", "")

        # Get all chapter texts
        cursor = await conn.execute(
            """SELECT chapter_index, scene_index, title, content
               FROM chapter_texts ORDER BY chapter_index, scene_index"""
        )
        rows = await cursor.fetchall()
        await conn.close()

        if not rows:
            return {"title": title, "genre": genre, "chapters": [], "full_text": "", "word_count": 0}

        # Group by chapter
        chapters = {}
        for r in rows:
            ci = r["chapter_index"]
            if ci not in chapters:
                chapters[ci] = {"chapter_index": ci, "title": r["title"], "scenes": []}
            chapters[ci]["scenes"].append(r["content"])

        # Build full text
        parts = [f"# {title}\n"]
        chapter_list = []
        for ci in sorted(chapters.keys()):
            ch = chapters[ci]
            chapter_text = "\n\n".join(ch["scenes"])
            parts.append(f"\n## 第{ci + 1}章 {ch['title']}\n")
            parts.append(chapter_text)
            chapter_list.append({
                "chapter_index": ci,
                "title": ch["title"],
                "text": chapter_text,
                "word_count": len(chapter_text),
            })

        full_text = "\n".join(parts)
        return {
            "title": title,
            "genre": genre,
            "chapters": chapter_list,
            "full_text": full_text,
            "word_count": len(full_text),
        }
    except Exception as e:
        return {"error": str(e), "title": "", "genre": "", "chapters": [], "full_text": "", "word_count": 0}


@router.get("/worlds/{novel_id}/export/markdown")
async def api_export_markdown(novel_id: str):
    """Export the full novel as Markdown text."""
    try:
        novel = get_novel_by_id(novel_id)
        if novel is None:
            return PlainTextResponse("未找到该世界", status_code=404)

        conn = await get_connection(novel.db_path)
        cursor0 = await conn.execute("SELECT outline_json FROM story_outline WHERE id = 1")
        row0 = await cursor0.fetchone()
        outline = json.loads(row0["outline_json"]) if row0 else {}
        title = outline.get("title", novel.title)

        cursor = await conn.execute(
            "SELECT chapter_index, scene_index, title, content "
            "FROM chapter_texts ORDER BY chapter_index, scene_index"
        )
        rows = await cursor.fetchall()
        await conn.close()

        if not rows:
            return PlainTextResponse("暂无章节内容", status_code=404)

        chapters: dict[int, dict] = {}
        for r in rows:
            ci = r["chapter_index"]
            if ci not in chapters:
                chapters[ci] = {"title": r["title"], "scenes": []}
            chapters[ci]["scenes"].append(r["content"])

        parts = [f"# {title}\n"]
        for ci in sorted(chapters.keys()):
            ch = chapters[ci]
            parts.append(f"\n## 第{ci + 1}章 {ch['title']}\n")
            parts.append("\n\n".join(ch["scenes"]))

        full_text = "\n".join(parts)
        safe_filename = quote(f"{novel_id}.md")
        return PlainTextResponse(
            full_text,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}",
            },
        )
    except Exception as e:
        return PlainTextResponse(f"导出失败: {e}", status_code=500)


@router.get("/worlds/{novel_id}/export/json")
async def api_export_json(novel_id: str):
    """Export the full world data as JSON (outline, characters, world, timeline, etc.)."""
    try:
        novel = get_novel_by_id(novel_id)
        if novel is None:
            return {"error": "not found"}

        conn = await get_connection(novel.db_path)

        # Outline
        cursor = await conn.execute("SELECT outline_json FROM story_outline WHERE id = 1")
        row = await cursor.fetchone()
        outline = json.loads(row["outline_json"]) if row else None

        # World
        cursor = await conn.execute("SELECT world_json FROM world_building WHERE id = 1")
        row = await cursor.fetchone()
        world = json.loads(row["world_json"]) if row else None

        # Characters
        cursor = await conn.execute("SELECT character_id, profile_json FROM characters")
        characters = [json.loads(r["profile_json"]) for r in await cursor.fetchall()]

        # Relationships
        cursor = await conn.execute("SELECT * FROM relationships")
        rels = [dict(r) for r in await cursor.fetchall()]

        # Propositions
        cursor = await conn.execute("SELECT what_is, where_from, where_to FROM world_propositions WHERE id = 1")
        prop_row = await cursor.fetchone()
        propositions = dict(prop_row) if prop_row else {}

        await conn.close()

        return {
            "novel_id": novel_id,
            "title": novel.title,
            "genre": novel.genre,
            "propositions": propositions,
            "outline": outline,
            "world": world,
            "characters": characters,
            "relationships": rels,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/worlds/{novel_id}/files")
async def api_list_world_files(novel_id: str):
    """List all downloadable files in a novel's workspace."""
    try:
        novel = get_novel_by_id(novel_id)
        if novel is None:
            return {"files": []}

        novel_dir = Path(novel.db_path).parent
        files = []

        # Historian output files
        historian_dir = novel_dir / "historian"
        if historian_dir.exists():
            for f in sorted(historian_dir.iterdir()):
                if f.is_file():
                    files.append({
                        "name": f.name,
                        "path": f"historian/{f.name}",
                        "size": f.stat().st_size,
                        "source": "historian",
                    })

        # Agent files
        agents_dir = novel_dir / "agents"
        if agents_dir.exists():
            for char_dir in sorted(agents_dir.iterdir()):
                if char_dir.is_dir():
                    for f in sorted(char_dir.iterdir()):
                        if f.is_file():
                            files.append({
                                "name": f"{char_dir.name}/{f.name}",
                                "path": f"agents/{char_dir.name}/{f.name}",
                                "size": f.stat().st_size,
                                "source": "agent",
                            })

        return {"files": files, "total": len(files)}
    except Exception as e:
        return {"error": str(e), "files": []}


@router.get("/worlds/{novel_id}/files/download")
async def api_download_file(novel_id: str, path: str = Query(...)):
    """Download a specific file from a novel's workspace."""
    try:
        novel = get_novel_by_id(novel_id)
        if novel is None:
            return PlainTextResponse("not found", status_code=404)

        novel_dir = Path(novel.db_path).parent
        file_path = novel_dir / path

        # Security: ensure path stays within novel_dir
        if not str(file_path.resolve()).startswith(str(novel_dir.resolve())):
            return PlainTextResponse("forbidden", status_code=403)

        if not file_path.exists():
            return PlainTextResponse("file not found", status_code=404)

        return FileResponse(
            str(file_path),
            filename=file_path.name,
            media_type="application/octet-stream",
        )
    except Exception as e:
        return PlainTextResponse(f"error: {e}", status_code=500)
