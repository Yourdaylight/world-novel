"""Typer CLI entry point for WorldNovel."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from novel_creator.config import settings

app = typer.Typer(
    name="novel-creator",
    help="多Agent小说生成系统 — 每个角色都是独立的AI Agent",
    rich_markup_mode="rich",
)
console = Console()

# ── novels sub-command group ─────────────────────────────────────
novels_app = typer.Typer(
    name="novels",
    help="书架管理 — 列出、创建、切换、删除、导出小说",
)
app.add_typer(novels_app, name="novels")


@novels_app.callback(invoke_without_command=True)
def novels_list(ctx: typer.Context) -> None:
    """列出所有小说（书架）"""
    if ctx.invoked_subcommand is not None:
        return
    from novel_creator.memory.registry import list_novels, load_registry

    novels = list_novels()
    registry = load_registry()
    if not novels:
        console.print("[yellow]书架为空 — 使用 [bold]novel-creator novels create[/] 或 [bold]novel-creator generate[/] 来创建新小说[/]")
        return

    table = Table(title="📚 书架", show_lines=True)
    table.add_column("", width=3, justify="center")
    table.add_column("ID", style="cyan")
    table.add_column("标题", max_width=25)
    table.add_column("类型")
    table.add_column("进度", justify="center")
    table.add_column("字数", justify="right")
    table.add_column("状态", justify="center")
    table.add_column("创建时间")

    status_icons = {
        "idle": "⚪",
        "generating": "🔵",
        "paused": "🟡",
        "completed": "🟢",
    }

    for n in novels:
        is_active = "➤" if n.novel_id == registry.active_novel_id else ""
        progress = f"{n.chapters_completed}/{n.chapters_total}" if n.chapters_total else "-"
        table.add_row(
            is_active,
            n.novel_id,
            n.title,
            n.genre,
            progress,
            f"{n.word_count:,}" if n.word_count else "-",
            f"{status_icons.get(n.status, '❓')} {n.status}",
            str(n.created_at)[:16],
        )

    console.print(table)
    if registry.active_novel_id:
        console.print(f"\n[dim]当前活跃: [bold]{registry.active_novel_id}[/][/]")


@novels_app.command("create")
def novels_create(
    title: str = typer.Option(..., "--title", "-t", help="小说标题"),
    genre: str = typer.Option("武侠", "--genre", "-g", help="小说类型"),
    chapters: int = typer.Option(0, "--chapters", "-c", help="预计章节数"),
) -> None:
    """创建新小说项目"""
    from novel_creator.memory.registry import register_novel

    info = register_novel(title=title, genre=genre, num_chapters=chapters)
    console.print(f"[bold green]✅ 已创建小说: {info.title}[/]")
    console.print(f"   ID: {info.novel_id}")
    console.print(f"   数据库: {info.db_path}")
    console.print(f"   已设为当前活跃小说")


@novels_app.command("select")
def novels_select(
    novel_id: str = typer.Argument(help="要切换到的小说ID"),
) -> None:
    """切换当前活跃小说"""
    from novel_creator.memory.registry import set_active_novel

    try:
        info = set_active_novel(novel_id)
        console.print(f"[bold green]✅ 已切换到: {info.title} ({info.novel_id})[/]")
    except ValueError as e:
        console.print(f"[bold red]❌ {e}[/]")
        raise typer.Exit(1)


@novels_app.command("delete")
def novels_delete(
    novel_id: str = typer.Argument(help="要删除的小说ID"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="跳过确认"),
) -> None:
    """删除小说（包括数据库和目录）"""
    from novel_creator.memory.registry import delete_novel, get_novel_by_id

    novel = get_novel_by_id(novel_id)
    if novel is None:
        console.print(f"[bold red]❌ 未找到小说: {novel_id}[/]")
        raise typer.Exit(1)

    if not confirm:
        confirm = typer.confirm(f"确定要删除 {novel.title} ({novel.novel_id}) 吗？这将删除所有数据。")
        if not confirm:
            console.print("[yellow]已取消[/]")
            return

    if delete_novel(novel_id):
        console.print(f"[bold green]✅ 已删除: {novel.title}[/]")
    else:
        console.print(f"[bold red]❌ 删除失败[/]")


@novels_app.command("export")
def novels_export(
    novel_id: str = typer.Argument(None, help="小说ID (不指定则用当前活跃小说)"),
    output: str = typer.Option(None, "--output", "-o", help="输出文件路径"),
) -> None:
    """导出小说为 Markdown 文件"""
    from novel_creator.memory.registry import get_active_novel, get_novel_by_id

    if novel_id:
        novel = get_novel_by_id(novel_id)
    else:
        novel = get_active_novel()

    if novel is None:
        console.print("[bold red]❌ 未找到小说，请指定小说ID或先选择活跃小说[/]")
        raise typer.Exit(1)

    out_path = output or str(Path(novel.db_path).parent / "output.md")
    asyncio.run(_run_export(novel.db_path, out_path, novel.title))


async def _run_export(db_path: str, out_path: str, title: str) -> None:
    from novel_creator.memory.database import get_connection

    conn = await get_connection(db_path)

    # Get outline for title
    cursor0 = await conn.execute("SELECT outline_json FROM story_outline WHERE id = 1")
    row0 = await cursor0.fetchone()
    outline = json.loads(row0["outline_json"]) if row0 else {}
    novel_title = outline.get("title", title)

    # Get all chapter texts
    cursor = await conn.execute(
        """SELECT chapter_index, scene_index, title, content
           FROM chapter_texts ORDER BY chapter_index, scene_index"""
    )
    rows = await cursor.fetchall()
    await conn.close()

    if not rows:
        console.print("[yellow]该小说暂无章节文本[/]")
        return

    # Group by chapter and build markdown
    chapters: dict[int, dict] = {}
    for r in rows:
        ci = r["chapter_index"]
        if ci not in chapters:
            chapters[ci] = {"title": r["title"], "scenes": []}
        chapters[ci]["scenes"].append(r["content"])

    parts = [f"# {novel_title}\n"]
    for ci in sorted(chapters.keys()):
        ch = chapters[ci]
        parts.append(f"\n## 第{ci + 1}章 {ch['title']}\n")
        parts.append("\n\n".join(ch["scenes"]))

    full_text = "\n".join(parts)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(full_text, encoding="utf-8")
    console.print(f"[bold green]📖 已导出到: {out_path}[/]")
    console.print(f"   字数: {len(full_text)}")


# ── Helper: resolve effective db_path ─────────────────────────────

def _resolve_db_path(db_path: str | None) -> str:
    """Resolve the database path: CLI --db > active novel > settings default."""
    if db_path:
        return db_path
    from novel_creator.memory.registry import get_active_novel
    active = get_active_novel()
    if active:
        return active.db_path
    return settings.db_path


# ======================================================================
# generate
# ======================================================================

@app.command()
def generate(
    genre: str = typer.Option("武侠", "--genre", "-g", help="小说类型"),
    theme: str = typer.Option("成长与救赎", "--theme", "-t", help="核心主题"),
    premise: str = typer.Option(
        "一个失去记忆的少年在江湖中寻找自己的过去",
        "--premise", "-p", help="故事前提",
    ),
    num_chapters: int = typer.Option(3, "--chapters", "-c", help="章节数"),
    num_characters: int = typer.Option(3, "--characters", "-n", help="主要角色数"),
    num_volumes: int = typer.Option(0, "--volumes", "-v", help="卷数 (0=不分卷)"),
    output: str = typer.Option("output.md", "--output", "-o", help="输出文件路径"),
    db_path: str = typer.Option(None, "--db", help="数据库路径 (高级覆盖)"),
    chapter_by_chapter: bool = typer.Option(False, "--chapter-by-chapter", help="逐章生成模式 (每章后暂停)"),
    title: str = typer.Option(None, "--title", help="小说标题 (用于注册到书架)"),
) -> None:
    """生成完整小说 — 端到端的多Agent创作流水线"""
    from novel_creator.memory.registry import (
        get_active_novel, register_novel, update_novel_status,
    )

    # Resolve db_path: --db overrides everything
    if db_path:
        effective_db = db_path
        novel_id = None
    else:
        # Auto-register a new novel if no active novel
        active = get_active_novel()
        if active and active.status in ("idle", "paused"):
            # Ask if user wants to continue on existing or create new
            console.print(f"[yellow]当前活跃小说: {active.title} ({active.novel_id})[/]")
            console.print("[yellow]将创建新小说项目...[/]")

        novel_title = title or f"{genre}小说"
        info = register_novel(title=novel_title, genre=genre, num_chapters=num_chapters)
        effective_db = info.db_path
        novel_id = info.novel_id
        console.print(f"[dim]📚 已注册新小说: {info.title} ({info.novel_id})[/]")

    mode_label = "逐章" if chapter_by_chapter else "全量"
    console.print(Panel.fit(
        "[bold]🎭 多Agent小说生成系统 V3[/]\n"
        f"类型: {genre} | 主题: {theme}\n"
        f"章节: {num_chapters} | 角色: {num_characters}"
        + (f" | 卷: {num_volumes}" if num_volumes else "")
        + f" | 模式: {mode_label}",
        border_style="blue",
    ))

    # Update status to generating
    if novel_id:
        update_novel_status(novel_id, status="generating")

    asyncio.run(_run_generate(
        genre, theme, premise, num_chapters, num_characters,
        num_volumes, output, effective_db, chapter_by_chapter, novel_id,
    ))


async def _run_generate(
    genre: str, theme: str, premise: str,
    num_chapters: int, num_characters: int, num_volumes: int,
    output: str, db_path: str, chapter_by_chapter: bool,
    novel_id: str | None,
) -> None:
    from novel_creator.graph.builder import compile_novel_graph
    from novel_creator.memory.database import reset_database
    from novel_creator.memory.registry import update_novel_status

    effective_db = db_path
    await reset_database(effective_db)

    graph = compile_novel_graph()
    initial_state = {
        "genre": genre,
        "theme": theme,
        "premise": premise,
        "num_chapters": num_chapters,
        "num_characters": num_characters,
        "num_volumes": num_volumes,
        "db_path": effective_db,
        "current_chapter": 0,
        "current_scene": 0,
        "chapters_completed": [],
        "chapter_summaries": [],
        "character_actions": [],
        "phase": "directing",
        "generation_mode": "chapter_by_chapter" if chapter_by_chapter else "full",
        "pause_after_chapter": False,
        "foreshadows": [],
        "plot_threads": [],
        "foreshadow_issues": [],
    }

    result = await graph.ainvoke(initial_state)

    # If paused (chapter-by-chapter mode), note it
    if result.get("phase") != "done" and result.get("last_checkpoint_id"):
        console.print(f"\n[bold yellow]⏸ 已暂停于第{result['current_chapter']}章后[/]")
        console.print(f"  检查点: {result['last_checkpoint_id']}")
        console.print("  使用 [bold]novel-creator resume[/] 继续生成")
        if novel_id:
            update_novel_status(
                novel_id,
                status="paused",
                chapters_completed=result["current_chapter"],
                chapters_total=num_chapters,
            )

    novel = result.get("novel")
    if novel:
        Path(output).write_text(novel.full_text, encoding="utf-8")
        console.print(f"\n[bold green]📖 小说已保存到: {output}[/]")
        console.print(f"   标题: {novel.title}")
        console.print(f"   字数: {novel.word_count}")
        if novel_id:
            update_novel_status(
                novel_id,
                status="completed",
                chapters_completed=len(novel.chapters),
                chapters_total=num_chapters,
                word_count=novel.word_count,
            )
    elif not result.get("last_checkpoint_id"):
        console.print("[bold red]❌ 小说生成失败[/]")
        if novel_id:
            update_novel_status(novel_id, status="idle")


# ======================================================================
# resume
# ======================================================================

@app.command()
def resume(
    from_chapter: int = typer.Option(None, "--from-chapter", help="从指定章节恢复 (1-based)"),
    output: str = typer.Option("output.md", "--output", "-o", help="输出文件路径"),
    db_path: str = typer.Option(None, "--db", help="数据库路径"),
    chapter_by_chapter: bool = typer.Option(False, "--chapter-by-chapter", help="继续逐章模式"),
) -> None:
    """从检查点恢复生成"""
    effective_db = _resolve_db_path(db_path)
    console.print("[bold blue]🔄 从检查点恢复...[/]")
    asyncio.run(_run_resume(from_chapter, output, effective_db, chapter_by_chapter))


async def _run_resume(
    from_chapter: int | None, output: str, db_path: str, chapter_by_chapter: bool,
) -> None:
    from novel_creator.graph.builder import compile_resume_graph
    from novel_creator.memory.database import get_connection
    from novel_creator.memory import checkpoint_store, world_store, foreshadow_store
    from novel_creator.models.character import CharacterProfile
    from novel_creator.models.narrative import Chapter
    from novel_creator.models.story import StoryOutline
    from novel_creator.models.relationship import RelationshipGraph

    effective_db = db_path
    conn = await get_connection(effective_db)

    # Load latest checkpoint
    cp = await checkpoint_store.load_latest(conn)
    if cp is None:
        console.print("[bold red]❌ 没有找到检查点[/]")
        await conn.close()
        return

    console.print(f"  检查点: {cp.checkpoint_id}")
    console.print(f"  标题: {cp.novel_title}")
    console.print(f"  进度: {cp.completed_chapters}/{cp.total_chapters} 章")

    # Load world view and outline
    world = await world_store.load_world(conn)
    outline = await world_store.load_outline(conn)
    foreshadows = await foreshadow_store.get_all_foreshadows(conn)
    plot_threads = await foreshadow_store.get_all_plot_threads(conn)

    # V3: Load timeline
    from novel_creator.memory import timeline_store
    timeline = await timeline_store.load_timeline(conn)

    # V3: Import any human edits to agent files on resume
    try:
        from novel_creator.sync.agent_files import AgentFileSync
        novel_dir = Path(effective_db).parent
        sync_obj = AgentFileSync(novel_dir)
        imported = await sync_obj.import_all(conn)
        if imported:
            console.print(f"  [dim]📥 导入了 {imported} 个角色的编辑[/]")
    except Exception:
        pass

    if outline is None:
        console.print("[bold red]❌ 没有找到故事大纲[/]")
        await conn.close()
        return

    # Reconstruct state from checkpoint
    state_data = json.loads(cp.state_json)
    start_chapter = (from_chapter - 1) if from_chapter else cp.completed_chapters

    # Reconstruct characters from DB
    cursor = await conn.execute("SELECT character_id, profile_json FROM characters")
    rows = await cursor.fetchall()
    characters = [
        CharacterProfile.model_validate_json(row["profile_json"]) for row in rows
    ]

    # Reconstruct relationships from DB
    cursor = await conn.execute("SELECT * FROM relationships")
    rel_rows = await cursor.fetchall()
    from novel_creator.models.relationship import Relationship
    rels = [
        Relationship(
            source_id=r["source_id"], target_id=r["target_id"],
            relationship_type=r["relationship_type"],
            trust=r["trust"], affection=r["affection"],
            description=r["description"] or "",
        ) for r in rel_rows
    ]
    relationships = RelationshipGraph(relationships=rels)

    # Reconstruct completed chapters
    completed_chapters = []
    chapter_summaries = state_data.get("chapter_summaries", [])

    await conn.close()

    resume_state = {
        "genre": outline.genre,
        "theme": outline.theme,
        "premise": outline.premise,
        "num_chapters": len(outline.chapters),
        "num_characters": len(characters),
        "outline": outline,
        "characters": characters,
        "relationships": relationships,
        "world_view": world,
        "foreshadows": foreshadows,
        "plot_threads": plot_threads,
        "current_chapter": start_chapter,
        "current_scene": 0,
        "chapters_completed": completed_chapters,
        "chapter_summaries": chapter_summaries[:start_chapter],
        "character_actions": [],
        "phase": "simulating",
        "db_path": effective_db,
        "generation_mode": "chapter_by_chapter" if chapter_by_chapter else "full",
        "pause_after_chapter": False,
        "foreshadow_issues": [],
        "timeline": timeline,
        "god_decision": None,
    }

    graph = compile_resume_graph()
    result = await graph.ainvoke(resume_state)

    if result.get("phase") != "done" and result.get("last_checkpoint_id"):
        console.print(f"\n[bold yellow]⏸ 已暂停于第{result['current_chapter']}章后[/]")
        console.print(f"  检查点: {result['last_checkpoint_id']}")
        console.print("  使用 [bold]novel-creator resume[/] 继续生成")

    novel = result.get("novel")
    if novel:
        Path(output).write_text(novel.full_text, encoding="utf-8")
        console.print(f"\n[bold green]📖 小说已保存到: {output}[/]")
        console.print(f"   标题: {novel.title}")
        console.print(f"   字数: {novel.word_count}")


# ======================================================================
# review — foreshadow audit report
# ======================================================================

@app.command()
def review(
    chapter: int = typer.Option(None, "--chapter", "-c", help="查看指定章节的伏笔 (1-based)"),
    db_path: str = typer.Option(None, "--db", help="数据库路径"),
) -> None:
    """查看伏笔审查报告"""
    effective_db = _resolve_db_path(db_path)
    asyncio.run(_run_review(chapter, effective_db))


async def _run_review(chapter: int | None, db_path: str) -> None:
    from novel_creator.memory.database import get_connection
    from novel_creator.memory import foreshadow_store

    conn = await get_connection(db_path)

    all_fs = await foreshadow_store.get_all_foreshadows(conn)
    all_pt = await foreshadow_store.get_all_plot_threads(conn)
    await conn.close()

    if not all_fs:
        console.print("[yellow]暂无伏笔数据[/]")
        return

    table = Table(title="📊 伏笔状态报告", show_lines=True)
    table.add_column("ID", style="cyan")
    table.add_column("描述", max_width=40)
    table.add_column("重要性", justify="center")
    table.add_column("埋设章", justify="center")
    table.add_column("预期回收", justify="center")
    table.add_column("实际回收", justify="center")
    table.add_column("状态", justify="center")

    status_colors = {
        "planted": "🟢 已埋设",
        "reinforced": "🔵 已强化",
        "payoff": "✅ 已回收",
        "dangling": "🔴 悬空",
    }

    for fs in all_fs:
        if chapter and fs.planted_chapter != (chapter - 1) and fs.expected_payoff_chapter != (chapter - 1):
            continue
        table.add_row(
            fs.foreshadow_id,
            fs.description[:40],
            fs.importance,
            str(fs.planted_chapter + 1),
            str(fs.expected_payoff_chapter + 1),
            str(fs.actual_payoff_chapter + 1) if fs.actual_payoff_chapter is not None else "-",
            status_colors.get(fs.status.value, fs.status.value),
        )

    console.print(table)

    if all_pt:
        console.print("\n[bold]剧情线:[/]")
        for pt in all_pt:
            console.print(f"  [{pt.status}] {pt.name}: {pt.description[:60]}")


# ======================================================================
# world — view world-building
# ======================================================================

@app.command()
def world(
    db_path: str = typer.Option(None, "--db", help="数据库路径"),
) -> None:
    """查看世界观设定"""
    effective_db = _resolve_db_path(db_path)
    asyncio.run(_run_world(effective_db))


async def _run_world(db_path: str) -> None:
    from novel_creator.memory.database import get_connection
    from novel_creator.memory.world_store import load_world

    conn = await get_connection(db_path)
    w = await load_world(conn)
    await conn.close()

    if w is None:
        console.print("[yellow]暂无世界观数据，请先运行生成命令[/]")
        return

    console.print(Panel.fit(f"[bold]🌍 {w.world_name}[/]\n{w.world_description}", border_style="cyan"))

    if w.power_systems:
        console.print("\n[bold]⚔️ 力量体系:[/]")
        for ps in w.power_systems:
            console.print(f"  [cyan]{ps.name}[/]: {ps.description}")
            if ps.levels:
                console.print(f"    等级: {' → '.join(ps.levels)}")

    if w.factions:
        console.print("\n[bold]🏴 势力:[/]")
        for f in w.factions:
            console.print(f"  [cyan]{f.name}[/]: {f.description} (领袖: {f.leader})")

    if w.locations:
        console.print("\n[bold]📍 重要地点:[/]")
        for loc in w.locations:
            console.print(f"  [cyan]{loc.name}[/]: {loc.description}")

    if w.history:
        console.print("\n[bold]📜 历史大事记:[/]")
        for h in w.history:
            console.print(f"  [{h.era}] {h.name}: {h.description}")


# ======================================================================
# status — generation progress and checkpoints
# ======================================================================

@app.command()
def status(
    db_path: str = typer.Option(None, "--db", help="数据库路径"),
) -> None:
    """查看生成进度和检查点列表"""
    effective_db = _resolve_db_path(db_path)
    asyncio.run(_run_status(effective_db))


async def _run_status(db_path: str) -> None:
    from novel_creator.memory.database import get_connection
    from novel_creator.memory import checkpoint_store

    conn = await get_connection(db_path)
    checkpoints = await checkpoint_store.list_all(conn)
    await conn.close()

    if not checkpoints:
        console.print("[yellow]暂无检查点数据[/]")
        return

    table = Table(title="💾 检查点列表", show_lines=True)
    table.add_column("ID", style="cyan")
    table.add_column("标题", max_width=30)
    table.add_column("进度", justify="center")
    table.add_column("阶段", justify="center")
    table.add_column("时间")

    for cp in checkpoints:
        progress = f"{cp.completed_chapters}/{cp.total_chapters}"
        table.add_row(
            cp.checkpoint_id,
            cp.novel_title[:30],
            progress,
            cp.phase,
            str(cp.created_at)[:19],
        )

    console.print(table)


# ======================================================================
# plan
# ======================================================================

@app.command()
def plan(
    genre: str = typer.Option("悬疑", "--genre", "-g", help="小说类型"),
    theme: str = typer.Option("真相与谎言", "--theme", "-t", help="核心主题"),
    premise: str = typer.Option(
        "一桩密室杀人案，所有嫌疑人都有不在场证明",
        "--premise", "-p", help="故事前提",
    ),
    num_chapters: int = typer.Option(3, "--chapters", "-c", help="章节数"),
    num_characters: int = typer.Option(3, "--characters", "-n", help="主要角色数"),
) -> None:
    """仅运行导演Agent — 生成故事大纲和角色设定"""
    console.print("[bold blue]🎬 导演Agent规划中...[/]")
    asyncio.run(_run_plan(genre, theme, premise, num_chapters, num_characters))


async def _run_plan(
    genre: str, theme: str, premise: str,
    num_chapters: int, num_characters: int,
) -> None:
    from novel_creator.agents.director import run_director

    result = await run_director(genre, theme, premise, num_chapters, num_characters)

    console.print(Panel.fit(f"[bold]{result.outline.title}[/]", border_style="green"))
    console.print(f"[dim]类型: {result.outline.genre} | 主题: {result.outline.theme}[/]")
    console.print(f"[dim]背景: {result.outline.setting}[/]")
    console.print(f"[dim]核心冲突: {result.outline.central_conflict}[/]\n")

    for ch in result.outline.chapters:
        console.print(f"[bold]第{ch.chapter_index+1}章: {ch.title}[/]")
        console.print(f"  {ch.summary}")
        for s in ch.scenes:
            console.print(f"  [dim]  场景{s.scene_index+1}: {s.location} — {s.objective}[/]")
        console.print()

    console.print("[bold]角色列表:[/]")
    for c in result.characters:
        console.print(f"  [cyan]{c.name}[/] ({c.role}) — {c.backstory[:60]}...")

    console.print(f"\n[bold]关系网络:[/]")
    for r in result.relationships.relationships:
        console.print(f"  {r.source_id} → {r.target_id}: {r.relationship_type} (信任:{r.trust:+.1f})")


# ======================================================================
# web
# ======================================================================

@app.command()
def web(
    host: str = typer.Option("0.0.0.0", "--host", help="服务器地址"),
    port: int = typer.Option(8000, "--port", help="服务器端口"),
) -> None:
    """启动Web仪表板"""
    import uvicorn
    console.print(f"[bold blue]🌐 启动Web仪表板: http://{host}:{port}[/]")
    uvicorn.run("novel_creator.web.app:app", host=host, port=port, reload=False)


# ======================================================================
# V3: timeline
# ======================================================================

@app.command()
def timeline(
    db_path: str = typer.Option(None, "--db", help="数据库路径"),
) -> None:
    """查看故事时间线 (时代+事件)"""
    effective_db = _resolve_db_path(db_path)
    asyncio.run(_run_timeline(effective_db))


async def _run_timeline(db_path: str) -> None:
    from novel_creator.memory.database import get_connection
    from novel_creator.memory import timeline_store

    conn = await get_connection(db_path)
    tl = await timeline_store.load_timeline(conn)
    decisions = await timeline_store.get_god_decisions(conn)
    await conn.close()

    if not tl.eras:
        console.print("[yellow]暂无时间线数据[/]")
        return

    console.print(Panel.fit("[bold]📅 故事时间线[/]", border_style="cyan"))

    for era in sorted(tl.eras, key=lambda e: e.order):
        era_events = tl.get_events_in_era(era.era_id)
        console.print(f"\n[bold cyan]【{era.name}】[/]")
        if era.story_time_start or era.story_time_end:
            console.print(f"  [dim]{era.story_time_start} — {era.story_time_end}[/]")
        console.print(f"  [dim]章节 {era.chapter_start + 1}-{era.chapter_end + 1}[/]")

        if era_events:
            table = Table(show_lines=False, show_header=True, header_style="bold")
            table.add_column("章", width=4, justify="center")
            table.add_column("类型", width=12)
            table.add_column("事件", max_width=40)
            table.add_column("重要度", width=6, justify="center")
            table.add_column("来源", width=10)
            for ev in sorted(era_events, key=lambda e: e.chapter_index):
                imp = "⭐" if ev.importance >= 0.7 else "·"
                table.add_row(
                    str(ev.chapter_index + 1),
                    ev.event_type,
                    f"{ev.title}: {ev.description[:40]}",
                    imp,
                    ev.source,
                )
            console.print(table)
        else:
            console.print("  [dim]暂无事件[/]")

    if decisions:
        console.print(f"\n[bold red]🔮 命运决策: {len(decisions)} 条[/]")
        for d in decisions:
            console.print(f"  [dim]第{d.chapter_index + 1}章后:[/] {d.summary()[:80]}")


# ======================================================================
# V3: sync
# ======================================================================

@app.command()
def sync(
    direction: str = typer.Option("export", "--direction", "-d", help="同步方向: export/import/both"),
    db_path: str = typer.Option(None, "--db", help="数据库路径"),
) -> None:
    """手动同步Agent文件"""
    effective_db = _resolve_db_path(db_path)
    asyncio.run(_run_sync(direction, effective_db))


async def _run_sync(direction: str, db_path: str) -> None:
    from novel_creator.memory.database import get_connection
    from novel_creator.memory import timeline_store
    from novel_creator.sync.agent_files import AgentFileSync

    conn = await get_connection(db_path)
    novel_dir = Path(db_path).parent
    sync_obj = AgentFileSync(novel_dir)

    tl = await timeline_store.load_timeline(conn)

    if direction in ("export", "both"):
        console.print("[bold blue]📤 导出Agent文件...[/]")
        await sync_obj.export_all(conn, tl)
        console.print(f"[green]✅ 导出完成到 {sync_obj.agents_dir}[/]")

    if direction in ("import", "both"):
        console.print("[bold blue]📥 导入Agent文件编辑...[/]")
        count = await sync_obj.import_all(conn)
        console.print(f"[green]✅ 导入完成, {count} 个角色已更新[/]")

    await conn.close()


# ======================================================================
# V3: agents
# ======================================================================

@app.command()
def agents(
    db_path: str = typer.Option(None, "--db", help="数据库路径"),
) -> None:
    """查看所有Agent文件状态"""
    effective_db = _resolve_db_path(db_path)
    asyncio.run(_run_agents(effective_db))


async def _run_agents(db_path: str) -> None:
    novel_dir = Path(db_path).parent
    agents_dir = novel_dir / "agents"

    if not agents_dir.exists():
        console.print("[yellow]暂无Agent文件 — 使用 [bold]novel-creator sync --direction export[/] 导出[/]")
        return

    table = Table(title="📁 Agent文件状态", show_lines=True)
    table.add_column("角色ID", style="cyan")
    table.add_column("agent.md", justify="center")
    table.add_column("soul.md", justify="center")
    table.add_column("memories/", justify="center")

    for entry in sorted(agents_dir.iterdir()):
        if entry.is_dir():
            has_agent = (entry / "agent.md").exists()
            has_soul = (entry / "soul.md").exists()
            memories_dir = entry / "memories"
            memory_count = len(list(memories_dir.iterdir())) if memories_dir.exists() else 0
            table.add_row(
                entry.name,
                "✅" if has_agent else "❌",
                "✅" if has_soul else "❌",
                f"✅ ({memory_count} files)" if memory_count > 0 else "❌",
            )

    console.print(table)


if __name__ == "__main__":
    app()
