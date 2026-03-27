"""LangGraph node functions — each node is a step in the pipeline."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from novel_creator.agents.character import CharacterAgent
from novel_creator.agents.director import run_director
from novel_creator.agents.reviewer import ReviewerAgent
from novel_creator.agents.writer import WriterAgent
from novel_creator.config import settings
from novel_creator.graph.state import NovelGenerationState
from novel_creator.llm import get_llm, invoke_with_retry, TokenTracker
from novel_creator.log import get_logger
from novel_creator.memory.character_memory import CharacterMemory
from novel_creator.memory.database import get_connection
from novel_creator.models.foreshadow import Foreshadow, ForeshadowStatus, PlotThread
from novel_creator.models.memory import EmotionalState
from novel_creator.models.narrative import Chapter, NovelOutput
from novel_creator.models.relationship import Relationship
from novel_creator.models.story import Volume
from novel_creator.models.timeline import StoryEra, StoryTimeline, TimelineEvent
from novel_creator.models.world import WorldView
from novel_creator.web.events import emit_event

logger = get_logger("novel_creator.graph")


# ======================================================================
# Director node
# ======================================================================

async def director_node(state: NovelGenerationState) -> dict:
    """Run the Director agent to generate story outline, characters, and relationships."""
    logger.info("[bold blue]🎬 导演Agent正在规划故事...[/]")
    await emit_event("phase_change", {"phase": "directing"})

    # V4: Check for propositions in DB and inject into premise
    premise = state["premise"]
    db_path = state.get("db_path")
    if db_path:
        try:
            conn_p = await get_connection(db_path)
            cursor_p = await conn_p.execute(
                "SELECT what_is, where_from, where_to FROM world_propositions WHERE id = 1"
            )
            prop_row = await cursor_p.fetchone()
            await conn_p.close()
            if prop_row and any([prop_row["what_is"], prop_row["where_from"], prop_row["where_to"]]):
                enhanced_parts = []
                if prop_row["what_is"]:
                    enhanced_parts.append(f"【世界本质】{prop_row['what_is']}")
                if prop_row["where_from"]:
                    enhanced_parts.append(f"【世界起源】{prop_row['where_from']}")
                if prop_row["where_to"]:
                    enhanced_parts.append(f"【世界命运】{prop_row['where_to']}")
                if premise and not premise.startswith("【"):
                    enhanced_parts.append(f"【故事前提】{premise}")
                premise = "\n".join(enhanced_parts)
                logger.info("  [dim]📜 三个命题已注入导演上下文[/]")
        except Exception:
            pass  # Non-critical, continue with original premise

    result = await run_director(
        genre=state["genre"],
        theme=state["theme"],
        premise=premise,
        num_chapters=state.get("num_chapters", 3),
        num_characters=state.get("num_characters", 3),
        num_volumes=state.get("num_volumes", 0),
    )

    # Initialize character memories in DB
    db_path = state.get("db_path")
    conn = await get_connection(db_path)
    for char in result.characters:
        mem = CharacterMemory(conn, char.character_id)
        await mem.save_profile(char)

    # Initialize relationships in DB
    for rel in result.relationships.relationships:
        mem = CharacterMemory(conn, rel.source_id)
        await mem.relationships.upsert(rel)

    # Initialize emotional states
    for char in result.characters:
        mem = CharacterMemory(conn, char.character_id)
        await mem.emotional.save_state(EmotionalState(character_id=char.character_id))

    # V2: Save outline to DB
    from novel_creator.memory.world_store import save_outline
    await save_outline(conn, result.outline)

    # V2: Save volumes to DB
    for vol in result.outline.volumes:
        await conn.execute(
            """INSERT INTO volumes (volume_index, title, summary, theme, chapter_start, chapter_end, arc_goal)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(volume_index) DO UPDATE SET
                   title=excluded.title, summary=excluded.summary, theme=excluded.theme,
                   chapter_start=excluded.chapter_start, chapter_end=excluded.chapter_end,
                   arc_goal=excluded.arc_goal""",
            (vol.volume_index, vol.title, vol.summary, vol.theme,
             vol.chapter_start, vol.chapter_end, vol.arc_goal),
        )
    await conn.commit()

    # V3: Create initial timeline from volumes/chapters
    timeline = _create_initial_timeline(result.outline)
    from novel_creator.memory import timeline_store
    for era in timeline.eras:
        await timeline_store.save_era(conn, era)

    # V3: Initial export of agent files
    try:
        novel_dir = Path(db_path).parent if db_path else Path("data")
        from novel_creator.sync.agent_files import AgentFileSync
        sync = AgentFileSync(novel_dir)
        await sync.export_all(conn, timeline)
        logger.info("  [dim]📁 Agent文件已导出[/]")
    except Exception as e:
        logger.info(f"  [dim yellow]⚠️ Agent文件导出失败: {e}[/]")

    await conn.close()

    logger.info(f"[green]✅ 故事规划完成: {result.outline.title}[/]")
    logger.info(f"   {len(result.outline.chapters)} 章节, {len(result.characters)} 角色")
    if result.outline.volumes:
        logger.info(f"   {len(result.outline.volumes)} 卷")
    logger.info(f"   {len(timeline.eras)} 时代")

    return {
        "outline": result.outline,
        "characters": result.characters,
        "relationships": result.relationships,
        "current_chapter": 0,
        "current_scene": 0,
        "chapters_completed": [],
        "chapter_summaries": [],
        "character_actions": [],
        "phase": "world_building",
        "timeline": timeline,
    }


def _create_initial_timeline(outline) -> StoryTimeline:
    """Create initial eras from volumes or a single era for the whole story."""
    eras: list[StoryEra] = []

    if outline.volumes:
        for vol in outline.volumes:
            era = StoryEra(
                era_id=f"era_vol{vol.volume_index}",
                name=vol.title,
                description=vol.summary or vol.arc_goal,
                order=vol.volume_index,
                story_time_start="",
                story_time_end="",
                chapter_start=vol.chapter_start,
                chapter_end=vol.chapter_end,
                volume_index=vol.volume_index,
            )
            eras.append(era)
    else:
        # Single era covering all chapters
        era = StoryEra(
            era_id="era_main",
            name="主线",
            description=outline.premise,
            order=0,
            story_time_start="",
            story_time_end="",
            chapter_start=0,
            chapter_end=max(0, len(outline.chapters) - 1),
            volume_index=0,
        )
        eras.append(era)

    return StoryTimeline(eras=eras, events=[])


# ======================================================================
# World-building node
# ======================================================================

class _WorldBuildingOutput(BaseModel):
    world_view: WorldView = Field(description="完整世界观")


_WORLD_BUILDER_PROMPT = (
    Path(__file__).parent.parent / "prompts" / "world_builder.md"
).read_text()


async def world_building_node(state: NovelGenerationState) -> dict:
    """Generate a structured WorldView based on the outline and characters."""
    logger.info("[bold cyan]🌍 世界构建Agent正在构建世界观...[/]")
    await emit_event("phase_change", {"phase": "world_building"})

    outline = state["outline"]
    characters = state["characters"]

    char_summary = "\n".join(
        f"- {c.name} ({c.role}): {c.backstory[:80]}..." for c in characters
    )
    chapter_summary = "\n".join(
        f"- 第{ch.chapter_index+1}章 {ch.title}: {ch.summary[:60]}" for ch in outline.chapters
    )

    llm = get_llm("director")
    structured_llm = llm.with_structured_output(WorldView)
    prompt = ChatPromptTemplate.from_messages([
        ("system", _WORLD_BUILDER_PROMPT),
        ("human", (
            f"## 故事大纲\n"
            f"**标题**: {outline.title}\n"
            f"**类型**: {outline.genre}\n"
            f"**主题**: {outline.theme}\n"
            f"**前提**: {outline.premise}\n"
            f"**背景**: {outline.setting}\n"
            f"**核心冲突**: {outline.central_conflict}\n\n"
            f"## 角色列表\n{char_summary}\n\n"
            f"## 章节结构\n{chapter_summary}\n\n"
            "请为这个故事构建完整的世界观。"
        )),
    ])
    chain = prompt | structured_llm
    world: WorldView = await invoke_with_retry(
        chain, {}, description="World building",
        role="director",
    )

    # Persist
    db_path = state.get("db_path")
    conn = await get_connection(db_path)
    from novel_creator.memory.world_store import save_world
    await save_world(conn, world)
    await conn.close()

    logger.info(f"[green]✅ 世界观构建完成: {world.world_name}[/]")
    logger.info(f"   {len(world.power_systems)} 力量体系, {len(world.locations)} 地点, {len(world.factions)} 势力")

    return {
        "world_view": world,
        "phase": "foreshadow_planning",
    }


# ======================================================================
# Foreshadow planning node
# ======================================================================

class _SceneAssignment(BaseModel):
    chapter_index: int = Field(description="章节序号")
    scene_index: int = Field(description="场景序号")
    foreshadows_to_plant: list[str] = Field(default_factory=list, description="需要埋设的伏笔ID")
    foreshadows_to_payoff: list[str] = Field(default_factory=list, description="需要回收的伏笔ID")


class _ForeshadowPlanOutput(BaseModel):
    foreshadows: list[Foreshadow] = Field(default_factory=list, description="伏笔列表")
    plot_threads: list[PlotThread] = Field(default_factory=list, description="剧情线列表")
    scene_assignments: list[_SceneAssignment] = Field(default_factory=list, description="场景伏笔分配")


_FORESHADOW_PLANNER_PROMPT = (
    Path(__file__).parent.parent / "prompts" / "foreshadow_planner.md"
).read_text()


async def foreshadow_plan_node(state: NovelGenerationState) -> dict:
    """Plan all foreshadows and plot threads for the story."""
    logger.info("[bold yellow]📊 伏笔规划Agent正在设计伏笔系统...[/]")
    await emit_event("phase_change", {"phase": "foreshadow_planning"})

    outline = state["outline"]
    characters = state["characters"]
    world = state.get("world_view")

    char_summary = "\n".join(
        f"- {c.name} ({c.role}): {c.backstory[:80]}..." for c in characters
    )
    chapter_detail = ""
    for ch in outline.chapters:
        chapter_detail += f"\n### 第{ch.chapter_index+1}章: {ch.title}\n{ch.summary}\n"
        for s in ch.scenes:
            chapter_detail += f"  - 场景{s.scene_index+1}: {s.location} — {s.objective}\n"

    world_summary = world.summary() if world else outline.setting

    llm = get_llm("director", temperature=0.7)
    structured_llm = llm.with_structured_output(_ForeshadowPlanOutput)
    prompt = ChatPromptTemplate.from_messages([
        ("system", _FORESHADOW_PLANNER_PROMPT),
        ("human", (
            f"## 故事大纲\n标题: {outline.title} | 类型: {outline.genre}\n"
            f"核心冲突: {outline.central_conflict}\n"
            f"结局走向: {outline.resolution_direction}\n\n"
            f"## 角色\n{char_summary}\n\n"
            f"## 世界观\n{world_summary}\n\n"
            f"## 章节与场景\n{chapter_detail}\n\n"
            "请规划伏笔系统和剧情线，并为每个场景分配伏笔。"
        )),
    ])
    chain = prompt | structured_llm
    plan: _ForeshadowPlanOutput = await invoke_with_retry(
        chain, {}, description="Foreshadow planning",
        role="director",
    )

    # Save to DB
    db_path = state.get("db_path")
    conn = await get_connection(db_path)
    from novel_creator.memory import foreshadow_store

    for fs in plan.foreshadows:
        await foreshadow_store.save_foreshadow(conn, fs)
    for pt in plan.plot_threads:
        await foreshadow_store.save_plot_thread(conn, pt)

    # Apply scene assignments to the outline
    outline_copy = outline.model_copy(deep=True)
    for sa in plan.scene_assignments:
        if sa.chapter_index < len(outline_copy.chapters):
            ch = outline_copy.chapters[sa.chapter_index]
            for scene in ch.scenes:
                if scene.scene_index == sa.scene_index:
                    scene.foreshadows_to_plant = sa.foreshadows_to_plant
                    scene.foreshadows_to_payoff = sa.foreshadows_to_payoff

    # Update outline in DB
    from novel_creator.memory.world_store import save_outline
    await save_outline(conn, outline_copy)
    await conn.close()

    logger.info(f"[green]✅ 伏笔规划完成: {len(plan.foreshadows)} 伏笔, {len(plan.plot_threads)} 剧情线[/]")

    # Flush token usage & emit foreshadow update
    await TokenTracker.flush(state.get("db_path"))
    await emit_event("foreshadows_updated", {})

    return {
        "outline": outline_copy,
        "foreshadows": plan.foreshadows,
        "plot_threads": plan.plot_threads,
        "phase": "simulating",
    }


# ======================================================================
# Scene simulation node (updated with world + timeline context)
# ======================================================================

async def simulate_scene_node(state: NovelGenerationState) -> dict:
    """Simulate a single scene: each character acts independently, then reacts."""
    chapter_idx = state["current_chapter"]
    scene_idx = state["current_scene"]
    outline = state["outline"]
    chapter_outline = outline.chapters[chapter_idx]
    scene_beat = chapter_outline.scenes[scene_idx]

    logger.info(
        f"[bold yellow]🎭 模拟场景: 第{chapter_idx+1}章 场景{scene_idx+1} — {scene_beat.location}[/]"
    )
    await emit_event("phase_change", {
        "phase": "simulating", "chapter": chapter_idx, "scene": scene_idx,
    })

    db_path = state.get("db_path")
    conn = await get_connection(db_path)

    # V2: Prepare world context
    world = state.get("world_view")
    world_context = world.summary() if world else ""
    location_detail = ""
    if world:
        loc = world.get_location(scene_beat.location)
        if loc:
            location_detail = f"{loc.name}: {loc.description}\n意义: {loc.significance}"

    # V3: Timeline context
    timeline = state.get("timeline")

    # V3: God decision guidance for this chapter
    god_decision = state.get("god_decision")
    god_guidance = ""
    if god_decision and god_decision.next_chapter_guidance:
        god_guidance = god_decision.next_chapter_guidance

    # Create character agents for involved characters
    involved_ids = scene_beat.involved_characters
    agents: dict[str, CharacterAgent] = {}

    # V3: Determine agent_dir for soul.md injection
    novel_dir = Path(db_path).parent if db_path else None

    for cid in involved_ids:
        mem = CharacterMemory(conn, cid)
        agent_dir = (novel_dir / "agents" / cid) if novel_dir else None
        agents[cid] = CharacterAgent(cid, mem, agent_dir=agent_dir)

    # --- Round 1: Independent actions (parallel) ---
    logger.info("  [dim]第一轮: 独立行动...[/]")
    round1_tasks = [
        agent.process_scene(
            chapter_index=chapter_idx,
            scene_index=scene_idx,
            location=scene_beat.location,
            scene_objective=scene_beat.objective,
            present_character_ids=involved_ids,
            other_actions=None,
            world_context=world_context,
            location_detail=location_detail,
            timeline=timeline,
        )
        for agent in agents.values()
    ]
    round1_results = await asyncio.gather(*round1_tasks, return_exceptions=True)

    all_actions = []
    round1_actions = []
    for result in round1_results:
        if isinstance(result, Exception):
            logger.info(f"  [red]⚠️ 角色行动失败: {result}[/]")
            continue
        round1_actions.extend(result)
        all_actions.extend(result)

    # --- Round 2: Reactions to others (parallel) ---
    logger.info("  [dim]第二轮: 互相反应...[/]")
    round2_tasks = [
        agent.process_scene(
            chapter_index=chapter_idx,
            scene_index=scene_idx,
            location=scene_beat.location,
            scene_objective=scene_beat.objective,
            present_character_ids=involved_ids,
            other_actions=[a for a in round1_actions if a.character_id != cid],
            world_context=world_context,
            location_detail=location_detail,
            timeline=timeline,
        )
        for cid, agent in agents.items()
    ]
    round2_results = await asyncio.gather(*round2_tasks, return_exceptions=True)

    for result in round2_results:
        if isinstance(result, Exception):
            logger.info(f"  [red]⚠️ 角色反应失败: {result}[/]")
            continue
        all_actions.extend(result)

    await conn.close()

    logger.info(f"  [green]✅ 场景模拟完成: {len(all_actions)} 个行动[/]")
    await emit_event("scene_simulated", {
        "chapter": chapter_idx, "scene": scene_idx, "action_count": len(all_actions),
    })

    # Flush token usage & emit relationship update
    await TokenTracker.flush(state.get("db_path"))
    await emit_event("relationships_updated", {})

    return {
        "character_actions": state.get("character_actions", []) + all_actions,
        "current_scene": scene_idx + 1,
    }


# ======================================================================
# Write chapter node (updated with god context + word count)
# ======================================================================

async def write_chapter_node(state: NovelGenerationState) -> dict:
    """Write the current chapter based on all simulated scene actions."""
    chapter_idx = state["current_chapter"]
    outline = state["outline"]
    chapter_outline = outline.chapters[chapter_idx]

    logger.info(f"[bold magenta]✍️ 写手Agent正在撰写第{chapter_idx+1}章: {chapter_outline.title}[/]")
    await emit_event("phase_change", {"phase": "writing", "chapter": chapter_idx})

    writer = WriterAgent()

    # Build character profiles dict
    char_profiles = {}
    for c in state["characters"]:
        char_profiles[c.character_id] = f"{c.name} ({c.role}) — {c.speaking_style}"

    # Previous context
    prev_context = ""
    summaries = state.get("chapter_summaries", [])
    if summaries:
        prev_context = "\n".join(summaries[-2:])

    # V2: World context
    world = state.get("world_view")
    world_context = world.summary() if world else ""

    # V2: Load pending foreshadows for this chapter
    db_path = state.get("db_path")
    conn = await get_connection(db_path)
    from novel_creator.memory import foreshadow_store
    to_plant, to_payoff = await foreshadow_store.get_pending_for_chapter(conn, chapter_idx)
    await conn.close()

    # V3: Build god context for writer
    god_decision = state.get("god_decision")
    god_context = _build_god_context_for_writer(god_decision) if god_decision else ""

    # Write each scene
    scenes = []
    for scene_beat in chapter_outline.scenes:
        scene_actions = [
            a for a in state["character_actions"]
            if a.chapter_index == chapter_idx and a.scene_index == scene_beat.scene_index
        ]

        # V2: Build foreshadow instructions for this scene
        foreshadow_instructions = _build_foreshadow_instructions(scene_beat, to_plant, to_payoff)

        # V2: Location description
        location_description = ""
        if world:
            loc = world.get_location(scene_beat.location)
            if loc:
                location_description = f"{loc.name}: {loc.description}"

        scene = await writer.write_scene(
            chapter_index=chapter_idx,
            scene_index=scene_beat.scene_index,
            location=scene_beat.location,
            scene_objective=scene_beat.objective,
            character_actions=scene_actions,
            character_profiles=char_profiles,
            previous_context=prev_context,
            world_context=world_context,
            location_description=location_description,
            foreshadow_instructions=foreshadow_instructions,
            god_context=god_context,
        )
        scenes.append(scene)
        logger.info(f"  [dim]场景{scene_beat.scene_index+1} 写作完成[/]")
        await emit_event("scene_written", {
            "chapter": chapter_idx,
            "scene": scene_beat.scene_index,
            "word_count": len(scene.content),
            "preview": scene.content[:200],
        })

    chapter = Chapter(
        chapter_index=chapter_idx,
        title=chapter_outline.title,
        scenes=scenes,
    )

    # Generate chapter summary for continuity
    summary = await writer.write_chapter_summary(chapter.full_text)

    # V2: Persist chapter text to DB for web dashboard
    db_path = state.get("db_path")
    conn = await get_connection(db_path)
    for scene in scenes:
        await conn.execute(
            """INSERT INTO chapter_texts (chapter_index, scene_index, title, content, pov_character, summary)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(chapter_index, scene_index) DO UPDATE SET
                   title=excluded.title, content=excluded.content,
                   pov_character=excluded.pov_character, summary=excluded.summary""",
            (chapter_idx, scene.scene_index, chapter_outline.title,
             scene.content, scene.pov_character, summary),
        )
    await conn.commit()
    await conn.close()

    word_count = len(chapter.full_text)
    logger.info(f"[green]✅ 第{chapter_idx+1}章写作完成 ({word_count} 字)[/]")

    # V3: Word count warning
    if word_count < 1500:
        logger.info(f"  [yellow]⚠️ 章节字数偏少 ({word_count}字)[/]")

    await emit_event("chapter_completed", {
        "chapter": chapter_idx,
        "title": chapter_outline.title,
        "word_count": word_count,
        "summary": summary[:200],
    })

    # Flush token usage & emit token update
    await TokenTracker.flush(state.get("db_path"))
    await emit_event("token_update", {"total_pending": TokenTracker.pending_total()})

    return {
        "chapters_completed": state.get("chapters_completed", []) + [chapter],
        "chapter_summaries": state.get("chapter_summaries", []) + [summary],
        "current_chapter": chapter_idx + 1,
        "current_scene": 0,
        "character_actions": [],  # Clear for next chapter
        "phase": "reviewing",
    }


def _build_god_context_for_writer(god_decision) -> str:
    """Build god context string for the writer agent."""
    parts: list[str] = []

    if god_decision.time_progression and god_decision.time_progression.time_skip:
        tp = god_decision.time_progression
        parts.append(f"⏳ 时间跳跃: {tp.time_skip}")
        if tp.description:
            parts.append(f"  {tp.description}")

    for we in god_decision.world_events:
        parts.append(f"🌍 世界事件 — {we.title}: {we.description}")

    for st in god_decision.subplot_triggers:
        parts.append(f"🔀 支线触发 — {st.trigger_type}: {st.description}")
        if st.setup:
            parts.append(f"  体现方式: {st.setup}")

    if god_decision.next_chapter_guidance:
        parts.append(f"📌 叙事指导: {god_decision.next_chapter_guidance}")

    return "\n".join(parts)


# ======================================================================
# God Agent node (V3)
# ======================================================================

async def god_agent_node(state: NovelGenerationState) -> dict:
    """Run the God Agent between chapters to determine world events and guidance."""
    chapter_idx = state["current_chapter"]  # Already incremented by write_chapter_node
    chapter_just_completed = chapter_idx - 1

    # Don't run god agent after the last chapter (we're about to compile)
    outline = state["outline"]
    if chapter_idx >= len(outline.chapters):
        return {}

    logger.info(f"[bold red]🔮 命运Agent正在审视第{chapter_just_completed + 1}章后的世界...[/]")
    await emit_event("phase_change", {"phase": "god_deliberation", "chapter": chapter_just_completed})

    from novel_creator.agents.god import GodAgent
    god = GodAgent()

    # Load timeline from state or DB
    timeline = state.get("timeline")
    db_path = state.get("db_path")
    if timeline is None:
        conn = await get_connection(db_path)
        from novel_creator.memory import timeline_store
        timeline = await timeline_store.load_timeline(conn)
        await conn.close()

    decision = await god.deliberate(
        chapter_just_completed=chapter_just_completed,
        outline=outline,
        characters=state.get("characters", []),
        world_view=state.get("world_view"),
        timeline=timeline,
        chapter_summaries=state.get("chapter_summaries", []),
        foreshadows=state.get("foreshadows"),
        plot_threads=state.get("plot_threads"),
    )

    logger.info(f"  [dim]{decision.summary()}[/]")

    # Persist decision and create timeline events
    conn = await get_connection(db_path)
    from novel_creator.memory import timeline_store

    await timeline_store.save_god_decision(conn, decision)

    # Create TimelineEvents from world events
    current_era = timeline.get_current_era(chapter_just_completed)
    era_id = current_era.era_id if current_era else "era_main"

    for we in decision.world_events:
        event = TimelineEvent(
            event_id=f"god_{decision.decision_id}_{uuid.uuid4().hex[:6]}",
            era_id=era_id,
            chapter_index=chapter_just_completed,
            story_time=we.story_time,
            event_type=we.event_type,
            title=we.title,
            description=we.description,
            affected_characters=we.affected_characters,
            affected_locations=we.affected_locations,
            source="god_agent",
            importance=we.importance,
        )
        await timeline_store.save_event(conn, event)
        timeline.events.append(event)

    # Handle new era from time progression
    if decision.time_progression and decision.time_progression.new_era:
        new_era = decision.time_progression.new_era
        await timeline_store.save_era(conn, new_era)
        timeline.eras.append(new_era)

    # Handle time skip event
    if decision.time_progression and decision.time_progression.time_skip:
        skip_event = TimelineEvent(
            event_id=f"skip_{decision.decision_id}",
            era_id=era_id,
            chapter_index=chapter_just_completed,
            story_time="",
            event_type="time_skip",
            title=f"时间跳跃: {decision.time_progression.time_skip}",
            description=decision.time_progression.description,
            affected_characters=[],
            affected_locations=[],
            source="god_agent",
            importance=0.6,
        )
        await timeline_store.save_event(conn, skip_event)
        timeline.events.append(skip_event)

    # V3: Sync agent files after god decision
    try:
        novel_dir = Path(db_path).parent if db_path else None
        if novel_dir:
            from novel_creator.sync.agent_files import AgentFileSync
            sync = AgentFileSync(novel_dir)
            await sync.export_god_agent(conn, timeline)
            # Also update character memories
            await sync.export_all(conn, timeline)
    except Exception:
        pass  # Non-critical

    await conn.close()

    await emit_event("god_decision", {
        "events": [we.title for we in decision.world_events],
        "time_skip": decision.time_progression.time_skip if decision.time_progression else "",
        "guidance": decision.next_chapter_guidance[:200],
    })

    # Flush token usage & emit timeline update
    await TokenTracker.flush(state.get("db_path"))
    await emit_event("timeline_updated", {})
    await emit_event("token_update", {"total_pending": TokenTracker.pending_total()})

    return {
        "god_decision": decision,
        "timeline": timeline,
    }


# ======================================================================
# Foreshadow check node
# ======================================================================

async def foreshadow_check_node(state: NovelGenerationState) -> dict:
    """Review the just-written chapter for foreshadowing compliance."""
    chapter_idx = state["current_chapter"] - 1  # write_chapter already incremented
    chapters = state.get("chapters_completed", [])
    if not chapters:
        return {"foreshadow_issues": [], "phase": "simulating"}

    chapter = chapters[-1]
    logger.info(f"[bold blue]🔍 审校Agent正在检查第{chapter_idx+1}章伏笔...[/]")

    db_path = state.get("db_path")
    conn = await get_connection(db_path)
    from novel_creator.memory import foreshadow_store

    to_plant, to_payoff = await foreshadow_store.get_pending_for_chapter(conn, chapter_idx)
    dangling = await foreshadow_store.get_dangling(conn, chapter_idx)

    issues: list[str] = []

    if to_plant or to_payoff or dangling:
        reviewer = ReviewerAgent()
        result = await reviewer.check_chapter(
            chapter_text=chapter.full_text,
            expected_plants=to_plant,
            expected_payoffs=to_payoff,
            dangling=dangling,
        )

        # Process results — mark payoffs
        for check in result.checks:
            if check.found and check.foreshadow_id in [f.foreshadow_id for f in to_payoff]:
                await foreshadow_store.mark_payoff(conn, check.foreshadow_id, chapter_idx)
            elif not check.found:
                issues.append(f"伏笔 {check.foreshadow_id} 未在第{chapter_idx+1}章中找到: {check.suggestion}")

        # Mark overdue dangling
        for d in dangling:
            await foreshadow_store.mark_dangling(conn, d.foreshadow_id)

        issues.extend(result.dangling_warnings)
        logger.info(f"  [dim]伏笔评分: {result.overall_score}/10[/]")
    else:
        logger.info("  [dim]本章无伏笔任务[/]")

    await conn.close()

    if issues:
        for issue in issues[:3]:
            logger.info(f"  [yellow]⚠️ {issue}[/]")

    # Emit foreshadow update event
    await emit_event("foreshadows_updated", {})

    return {
        "foreshadow_issues": state.get("foreshadow_issues", []) + issues,
        "phase": "simulating",
    }


# ======================================================================
# Checkpoint save node
# ======================================================================

async def checkpoint_save_node(state: NovelGenerationState) -> dict:
    """Save a checkpoint after each chapter for pause/resume support."""
    db_path = state.get("db_path")
    conn = await get_connection(db_path)
    from novel_creator.memory import checkpoint_store

    cp_id = await checkpoint_store.save_checkpoint(conn, state)
    await conn.close()

    chapter_idx = state["current_chapter"]
    logger.info(f"  [dim]💾 检查点已保存: {cp_id} (第{chapter_idx}章完成)[/]")

    await emit_event("checkpoint_saved", {
        "checkpoint_id": cp_id, "chapters_completed": chapter_idx,
    })

    # Update registry if this novel is registered
    try:
        from novel_creator.memory.registry import load_registry, update_novel_status
        registry = load_registry()
        for novel in registry.novels:
            if novel.db_path == db_path:
                # Calculate word count from completed chapters
                wc = sum(len(ch.full_text) for ch in state.get("chapters_completed", []))
                update_novel_status(
                    novel.novel_id,
                    status="paused" if state.get("generation_mode") == "chapter_by_chapter" else "generating",
                    chapters_completed=chapter_idx,
                    word_count=wc,
                )
                break
    except Exception:
        pass  # Don't fail the pipeline if registry update fails

    return {
        "last_checkpoint_id": cp_id,
    }


# ======================================================================
# Compile novel node
# ======================================================================

async def compile_novel_node(state: NovelGenerationState) -> dict:
    """Compile all chapters into the final novel output."""
    outline = state["outline"]
    novel = NovelOutput(
        title=outline.title,
        genre=outline.genre,
        chapters=state["chapters_completed"],
    )
    logger.info(f"\n[bold green]📖 小说完成: {novel.title}[/]")
    logger.info(f"   共 {len(novel.chapters)} 章, {novel.word_count} 字")

    await emit_event("novel_completed", {
        "title": novel.title,
        "total_chapters": len(novel.chapters),
        "word_count": novel.word_count,
    })

    # Update registry if this novel is registered
    try:
        db_path = state.get("db_path")
        from novel_creator.memory.registry import load_registry, update_novel_status
        registry = load_registry()
        for n in registry.novels:
            if n.db_path == db_path:
                update_novel_status(
                    n.novel_id,
                    status="completed",
                    chapters_completed=len(novel.chapters),
                    word_count=novel.word_count,
                )
                break
    except Exception:
        pass  # Don't fail the pipeline if registry update fails

    return {"novel": novel, "phase": "done"}


# ======================================================================
# Helpers
# ======================================================================

# ======================================================================
# Reflection node (V4 — character self-examination)
# ======================================================================

async def reflection_node(state: NovelGenerationState) -> dict:
    """Run character reflection after god_agent decisions."""
    chapter_idx = state["current_chapter"]  # Already incremented by write_chapter_node
    characters = state["characters"]
    db_path = state.get("db_path")

    # Don't run reflection after the last chapter (about to compile)
    outline = state["outline"]
    if chapter_idx >= len(outline.chapters):
        return {}

    conn = await get_connection(db_path)

    from novel_creator.agents.reflection import ReflectionAgent
    agent = ReflectionAgent()

    reflected_count = 0
    for char in characters:
        mem = CharacterMemory(conn, char.character_id)
        if await mem.reflections.should_reflect(chapter_idx, interval=2):
            output = await agent.reflect(char.character_id, mem, chapter_idx)
            reflected_count += 1
            logger.info(f"  角色 {char.name} 完成反思: {output.summary[:50]}...")

    await conn.close()

    if reflected_count > 0:
        logger.info(f"[green]✅ {reflected_count} 个角色完成了自我反思[/]")
        await emit_event("reflection_complete", {"chapter": chapter_idx, "count": reflected_count})

    return {}  # No state changes needed, reflection updates DB directly


# ======================================================================
# Helpers
# ======================================================================

def _build_foreshadow_instructions(
    scene_beat,
    to_plant: list[Foreshadow],
    to_payoff: list[Foreshadow],
) -> str:
    """Build foreshadow instructions string for the writer agent."""
    lines: list[str] = []

    # Foreshadows to plant in this scene
    plant_ids = set(scene_beat.foreshadows_to_plant)
    if plant_ids:
        for fs in to_plant:
            if fs.foreshadow_id in plant_ids:
                lines.append(f"🟢 请在叙事中自然埋入暗示: {fs.description} (参考: {fs.hint_text})")

    # Foreshadows to payoff in this scene
    payoff_ids = set(scene_beat.foreshadows_to_payoff)
    if payoff_ids:
        for fs in to_payoff:
            if fs.foreshadow_id in payoff_ids:
                lines.append(f"🔵 请在叙事中揭示/回收: {fs.description}")

    return "\n".join(lines)
