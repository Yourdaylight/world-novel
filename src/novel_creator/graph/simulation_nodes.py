"""V9: Node functions for the decoupled preparation and simulation graphs."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from novel_creator.agents.character import CharacterAgent
from novel_creator.agents.scene_graph import SceneGraph as SceneOrchestrator
from novel_creator.config import settings
from novel_creator.graph.state import PreparationState, SimulationState
from novel_creator.llm import get_llm, invoke_with_retry, TokenTracker
from novel_creator.log import get_logger
from novel_creator.memory.character_memory import CharacterMemory
from novel_creator.memory.database import get_connection
from novel_creator.models.character import CharacterProfile
from novel_creator.models.foreshadow import Foreshadow, PlotThread
from novel_creator.models.relationship import Relationship, RelationshipGraph
from novel_creator.models.simulation_beat import SimulationBeat
from novel_creator.models.timeline import StoryTimeline
from novel_creator.web.events import emit_event

logger = get_logger("novel_creator.graph.simulation")

# God checkpoint interval: run god_agent every N beats
GOD_CHECKPOINT_INTERVAL = 5


# ======================================================================
# Beat plan node (preparation graph)
# ======================================================================

class _BeatPlanOutput(BaseModel):
    beats: list[SimulationBeat] = Field(default_factory=list, description="扁平化的时间线节拍列表")


_BEAT_PLANNER_PROMPT = (
    Path(__file__).parent.parent / "prompts" / "beat_planner.md"
).read_text()


async def beat_plan_node(state: PreparationState) -> dict:
    """Generate a flat list of SimulationBeats from the outline + foreshadows, write to DB.

    This is the final node of the preparation graph.  It takes the
    chapter outlines (with their SceneBeat lists) and the foreshadow plan
    and produces a flat, timeline-ordered list of SimulationBeats.
    """
    logger.info("[bold cyan]📋 节拍规划Agent正在生成模拟节拍...[/]")
    await emit_event("phase_change", {"phase": "beat_planning"})

    outline = state["outline"]
    characters = state.get("characters", [])
    foreshadows = state.get("foreshadows", [])
    world = state.get("world_view")

    # Build context for LLM
    char_summary = "\n".join(
        f"- {c.character_id}: {c.name} ({c.role})" for c in characters
    )

    chapter_detail = ""
    for ch in outline.chapters:
        chapter_detail += f"\n### 第{ch.chapter_index + 1}章: {ch.title}\n"
        chapter_detail += f"概要: {ch.summary}\n"
        if ch.story_time:
            chapter_detail += f"时间: {ch.story_time}\n"
        if ch.era_id:
            chapter_detail += f"时代: {ch.era_id}\n"
        for s in ch.scenes:
            chapter_detail += (
                f"  - 场景{s.scene_index + 1}: {s.location} — {s.objective}"
                f" (角色: {', '.join(s.involved_characters)})\n"
            )
            if s.foreshadows_to_plant:
                chapter_detail += f"    埋伏笔: {', '.join(s.foreshadows_to_plant)}\n"
            if s.foreshadows_to_payoff:
                chapter_detail += f"    回收伏笔: {', '.join(s.foreshadows_to_payoff)}\n"

    fs_summary = ""
    if foreshadows:
        fs_lines = [f"- {fs.foreshadow_id}: {fs.description} (第{fs.planted_chapter + 1}章埋→第{fs.expected_payoff_chapter + 1}章收)"
                     for fs in foreshadows]
        fs_summary = "\n".join(fs_lines)

    world_summary = world.summary() if world else outline.setting

    llm = get_llm("director", temperature=0.7)
    structured_llm = llm.with_structured_output(_BeatPlanOutput)
    prompt = ChatPromptTemplate.from_messages([
        ("system", _BEAT_PLANNER_PROMPT),
        ("human", (
            f"## 故事大纲\n标题: {outline.title} | 类型: {outline.genre}\n"
            f"核心冲突: {outline.central_conflict}\n\n"
            f"## 角色\n{char_summary}\n\n"
            f"## 世界观\n{world_summary}\n\n"
            f"## 章节与场景\n{chapter_detail}\n\n"
            f"## 伏笔系统\n{fs_summary}\n\n"
            "请将以上章节场景转换为扁平的时间线节拍列表。"
        )),
    ])
    chain = prompt | structured_llm
    plan: _BeatPlanOutput = await invoke_with_retry(
        chain, {}, description="Beat planning",
        role="director",
    )

    beats = plan.beats

    # Fallback: if LLM returns empty, create beats from existing scenes
    if not beats:
        beats = _fallback_beats_from_outline(outline)

    # Ensure consistent beat_ids and sequences
    for i, beat in enumerate(beats):
        beat.sequence = i
        if not beat.beat_id:
            beat.beat_id = f"beat_{i:03d}"

    # Write beats to DB
    db_path = state.get("db_path")
    conn = await get_connection(db_path)
    for beat in beats:
        await conn.execute(
            """INSERT INTO simulation_beats
               (beat_id, sequence, story_time, era_id, location,
                involved_characters, objective, conflict, tone, status,
                suggested_chapter, parallel_group,
                foreshadows_to_plant, foreshadows_to_payoff)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(beat_id) DO UPDATE SET
                   sequence=excluded.sequence, story_time=excluded.story_time,
                   location=excluded.location, objective=excluded.objective""",
            (
                beat.beat_id, beat.sequence, beat.story_time, beat.era_id,
                beat.location, json.dumps(beat.involved_characters, ensure_ascii=False),
                beat.objective, beat.conflict, beat.tone, beat.status,
                beat.suggested_chapter, beat.parallel_group,
                json.dumps(beat.foreshadows_to_plant, ensure_ascii=False),
                json.dumps(beat.foreshadows_to_payoff, ensure_ascii=False),
            ),
        )

    # Update chapter outlines with beat_range
    outline_copy = outline.model_copy(deep=True)
    for ch in outline_copy.chapters:
        ch_beats = [b for b in beats if b.suggested_chapter == ch.chapter_index]
        if ch_beats:
            ch.beat_range_start = min(b.sequence for b in ch_beats)
            ch.beat_range_end = max(b.sequence for b in ch_beats)

    # Save updated outline
    from novel_creator.memory.world_store import save_outline
    await save_outline(conn, outline_copy)
    await conn.commit()
    await conn.close()

    logger.info(f"[green]节拍规划完成: {len(beats)} 个模拟节拍[/]")
    await emit_event("beat_plan_completed", {"beat_count": len(beats)})
    await TokenTracker.flush(state.get("db_path"))

    return {
        "outline": outline_copy,
        "simulation_beats": beats,
        "phase": "beat_plan_done",
    }


def _fallback_beats_from_outline(outline) -> list[SimulationBeat]:
    """Create SimulationBeats 1:1 from existing SceneBeats as fallback."""
    beats: list[SimulationBeat] = []
    seq = 0
    for ch in outline.chapters:
        for scene in ch.scenes:
            beat = SimulationBeat(
                beat_id=f"beat_{seq:03d}",
                sequence=seq,
                story_time=ch.story_time,
                era_id=ch.era_id,
                location=scene.location,
                involved_characters=scene.involved_characters,
                objective=scene.objective,
                conflict=scene.conflict,
                tone=scene.tone,
                status="pending",
                suggested_chapter=ch.chapter_index,
                foreshadows_to_plant=scene.foreshadows_to_plant,
                foreshadows_to_payoff=scene.foreshadows_to_payoff,
            )
            beats.append(beat)
            seq += 1
    return beats


# ======================================================================
# Simulation graph nodes
# ======================================================================

async def load_context_node(state: SimulationState) -> dict:
    """Load all needed context from DB at the start of each simulation loop."""
    logger.info("[bold blue]📂 加载模拟上下文...[/]")

    db_path = state["db_path"]
    conn = await get_connection(db_path)

    # Load outline
    from novel_creator.memory.world_store import load_outline, load_world
    outline = await load_outline(conn)
    world = await load_world(conn)

    # Load characters
    cursor = await conn.execute("SELECT character_id, profile_json FROM characters")
    rows = await cursor.fetchall()
    characters = [CharacterProfile.model_validate_json(row["profile_json"]) for row in rows]

    # Load relationships
    cursor2 = await conn.execute("SELECT * FROM relationships")
    rel_rows = await cursor2.fetchall()
    rels = [
        Relationship(
            source_id=r["source_id"], target_id=r["target_id"],
            relationship_type=r["relationship_type"],
            trust=r["trust"], affection=r["affection"],
            description=r["description"] or "",
        ) for r in rel_rows
    ]
    relationships = RelationshipGraph(relationships=rels)

    # Load foreshadows & plot threads
    from novel_creator.memory import foreshadow_store, timeline_store
    foreshadows = await foreshadow_store.get_all_foreshadows(conn)
    plot_threads = await foreshadow_store.get_all_plot_threads(conn)
    timeline = await timeline_store.load_timeline(conn)

    # Count beats
    cursor3 = await conn.execute("SELECT COUNT(*) FROM simulation_beats")
    total_row = await cursor3.fetchone()
    total_count = total_row[0] if total_row else 0

    cursor4 = await conn.execute("SELECT COUNT(*) FROM simulation_beats WHERE status = 'completed'")
    completed_row = await cursor4.fetchone()
    completed_count = completed_row[0] if completed_row else 0

    await conn.close()

    return {
        "outline": outline,
        "characters": characters,
        "relationships": relationships,
        "world_view": world,
        "timeline": timeline,
        "foreshadows": foreshadows,
        "plot_threads": plot_threads,
        "total_beat_count": total_count,
        "completed_beat_count": completed_count,
        "phase": "picking",
    }


async def pick_next_beats_node(state: SimulationState) -> dict:
    """Pick the next batch of beats to simulate from DB.

    Takes the next pending beat(s), including any in the same parallel_group.
    """
    db_path = state["db_path"]
    conn = await get_connection(db_path)

    # Get the next pending beat by sequence order
    cursor = await conn.execute(
        "SELECT * FROM simulation_beats WHERE status = 'pending' ORDER BY sequence LIMIT 1"
    )
    row = await cursor.fetchone()

    if row is None:
        await conn.close()
        logger.info("[green]所有节拍模拟完成[/]")
        return {"current_beats": [], "phase": "done"}

    first_beat = _row_to_beat(row)
    beats = [first_beat]

    # If it has a parallel_group, fetch all pending beats in that group
    if first_beat.parallel_group:
        cursor2 = await conn.execute(
            "SELECT * FROM simulation_beats WHERE parallel_group = ? AND status = 'pending' AND beat_id != ?",
            (first_beat.parallel_group, first_beat.beat_id),
        )
        for r in await cursor2.fetchall():
            beats.append(_row_to_beat(r))

    # Mark them as simulating
    for beat in beats:
        await conn.execute(
            "UPDATE simulation_beats SET status = 'simulating' WHERE beat_id = ?",
            (beat.beat_id,),
        )
        beat.status = "simulating"
    await conn.commit()
    await conn.close()

    beat_ids = [b.beat_id for b in beats]
    logger.info(f"[bold yellow]🎯 选取 {len(beats)} 个节拍: {', '.join(beat_ids)}[/]")
    await emit_event("beats_picked", {"beat_ids": beat_ids, "count": len(beats)})

    return {"current_beats": beats, "phase": "simulating"}


async def simulate_beats_node(state: SimulationState) -> dict:
    """Simulate the current batch of beats using SceneOrchestrator.

    If multiple beats are in the same parallel_group, they are simulated
    concurrently via asyncio.gather.
    """
    beats = state.get("current_beats", [])
    if not beats:
        return {"phase": "done"}

    db_path = state["db_path"]
    characters = state.get("characters", [])
    world = state.get("world_view")
    timeline = state.get("timeline")

    world_context = world.summary() if world else ""
    # Inject propositions
    from novel_creator.graph.nodes import _inject_propositions
    world_context = await _inject_propositions(db_path, world_context)

    char_name_map: dict[str, str] = {}
    for c in characters:
        char_name_map[c.character_id] = c.name

    novel_dir = Path(db_path).parent if db_path else None

    async def _simulate_one(beat: SimulationBeat) -> tuple[SimulationBeat, object]:
        """Simulate a single beat."""
        conn = await get_connection(db_path)

        scene_beat = beat.to_scene_beat()

        # Location detail
        location_detail = ""
        if world:
            loc = world.get_location(beat.location)
            if loc:
                location_detail = f"{loc.name}: {loc.description}\n意义: {loc.significance}"

        # Create character agents
        agents: dict[str, CharacterAgent] = {}
        for cid in beat.involved_characters:
            mem = CharacterMemory(conn, cid)
            agent_dir = (novel_dir / "agents" / cid) if novel_dir else None
            agents[cid] = CharacterAgent(cid, mem, agent_dir=agent_dir)

        orchestrator = SceneOrchestrator(
            agents=agents,
            scene_beat=scene_beat,
            chapter_index=beat.suggested_chapter or 0,
            scene_index=beat.sequence,
            world_context=world_context,
            location_detail=location_detail,
            timeline=timeline,
            char_name_map=char_name_map,
        )
        result = await orchestrator.run()

        # Persist scene result with beat_id
        await _persist_beat_result(conn, beat, result)
        await conn.close()

        return beat, result

    # Run beats in parallel if multiple, otherwise just run one
    if len(beats) > 1:
        logger.info(f"[bold yellow]⚡ 并行模拟 {len(beats)} 个节拍...[/]")
        results = await asyncio.gather(
            *[_simulate_one(b) for b in beats],
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"节拍模拟失败: {r}")
            else:
                beat, scene_result = r
                logger.info(
                    f"  [green]✅ {beat.beat_id} 完成: {scene_result.total_turns} 轮[/]"
                )
                await emit_event("beat_simulated", {
                    "beat_id": beat.beat_id,
                    "total_turns": scene_result.total_turns,
                    "ended_by": scene_result.ended_by,
                })
    else:
        beat, scene_result = await _simulate_one(beats[0])
        logger.info(
            f"  [green]✅ {beat.beat_id} 完成: {scene_result.total_turns} 轮[/]"
        )
        await emit_event("beat_simulated", {
            "beat_id": beat.beat_id,
            "total_turns": scene_result.total_turns,
            "ended_by": scene_result.ended_by,
        })

    await TokenTracker.flush(db_path)
    await emit_event("relationships_updated", {})

    return {"phase": "persisting"}


async def persist_results_node(state: SimulationState) -> dict:
    """Mark simulated beats as completed in DB."""
    beats = state.get("current_beats", [])
    db_path = state["db_path"]
    conn = await get_connection(db_path)

    for beat in beats:
        await conn.execute(
            "UPDATE simulation_beats SET status = 'completed' WHERE beat_id = ?",
            (beat.beat_id,),
        )
    await conn.commit()

    # Update completed count
    cursor = await conn.execute("SELECT COUNT(*) FROM simulation_beats WHERE status = 'completed'")
    row = await cursor.fetchone()
    completed = row[0] if row else 0
    await conn.close()

    beats_since = state.get("beats_since_checkpoint", 0) + len(beats)

    logger.info(f"  [dim]💾 {len(beats)} 节拍已持久化, 总完成: {completed}[/]")
    await emit_event("simulation_progress", {
        "completed": completed,
        "total": state.get("total_beat_count", 0),
    })

    return {
        "completed_beat_count": completed,
        "beats_since_checkpoint": beats_since,
        "phase": "checkpoint",
    }


async def god_checkpoint_node(state: SimulationState) -> dict:
    """Run god_agent + foreshadow_check + reflection every N beats."""
    beats_since = state.get("beats_since_checkpoint", 0)

    if beats_since < GOD_CHECKPOINT_INTERVAL:
        return {"phase": "picking"}  # Skip, go pick more beats

    logger.info(f"[bold red]🔮 命运检查点 (每{GOD_CHECKPOINT_INTERVAL}个节拍)...[/]")
    await emit_event("phase_change", {"phase": "god_checkpoint"})

    db_path = state["db_path"]
    outline = state.get("outline")
    characters = state.get("characters", [])
    world = state.get("world_view")
    timeline = state.get("timeline")
    foreshadows = state.get("foreshadows", [])
    plot_threads = state.get("plot_threads", [])

    # Determine which chapter we're roughly in based on completed beats
    completed_count = state.get("completed_beat_count", 0)
    approx_chapter = 0
    if outline:
        for ch in outline.chapters:
            if ch.beat_range_end is not None and completed_count > ch.beat_range_end:
                approx_chapter = ch.chapter_index + 1

    # Build chapter summaries from DB
    conn = await get_connection(db_path)
    cursor = await conn.execute(
        "SELECT DISTINCT chapter_index, summary FROM chapter_texts ORDER BY chapter_index"
    )
    summary_rows = await cursor.fetchall()
    chapter_summaries = [r["summary"] for r in summary_rows if r["summary"]]

    # Run god agent
    from novel_creator.agents.god import GodAgent
    god = GodAgent()

    try:
        decision = await god.deliberate(
            chapter_just_completed=max(0, approx_chapter - 1),
            outline=outline,
            characters=characters,
            world_view=world,
            timeline=timeline or StoryTimeline(eras=[], events=[]),
            chapter_summaries=chapter_summaries,
            foreshadows=foreshadows,
            plot_threads=plot_threads,
        )

        # Save decision
        from novel_creator.memory import timeline_store
        await timeline_store.save_god_decision(conn, decision)
        logger.info(f"  [dim]{decision.summary()}[/]")

        await emit_event("god_decision", {
            "events": [we.title for we in decision.world_events],
            "guidance": decision.next_chapter_guidance[:200],
        })
    except Exception as e:
        logger.error(f"命运检查点失败: {e}")

    # Run reflection for characters
    from novel_creator.agents.reflection import ReflectionAgent
    reflection_agent = ReflectionAgent()
    reflected = 0
    for char in characters:
        mem = CharacterMemory(conn, char.character_id)
        if await mem.reflections.should_reflect(approx_chapter, interval=2):
            try:
                await reflection_agent.reflect(char.character_id, mem, approx_chapter)
                reflected += 1
            except Exception:
                pass

    if reflected > 0:
        logger.info(f"  [green]{reflected} 个角色完成了自我反思[/]")

    await conn.close()
    await TokenTracker.flush(db_path)

    return {
        "beats_since_checkpoint": 0,
        "phase": "picking",
    }


# ======================================================================
# Simulation graph edge functions
# ======================================================================

def should_continue_simulation(state: SimulationState) -> str:
    """Determine whether to continue the simulation loop or stop."""
    if state.get("should_stop", False):
        return "done"
    if state.get("phase") == "done":
        return "done"
    beats = state.get("current_beats", [])
    if not beats:
        return "done"
    return "continue"


def should_run_checkpoint(state: SimulationState) -> str:
    """Determine whether to run god checkpoint or skip to picking."""
    beats_since = state.get("beats_since_checkpoint", 0)
    if beats_since >= GOD_CHECKPOINT_INTERVAL:
        return "checkpoint"
    return "pick"


# ======================================================================
# Helpers
# ======================================================================

def _row_to_beat(row) -> SimulationBeat:
    """Convert a DB row to a SimulationBeat."""
    return SimulationBeat(
        beat_id=row["beat_id"],
        sequence=row["sequence"],
        story_time=row["story_time"] or "",
        era_id=row["era_id"] or "",
        location=row["location"],
        involved_characters=json.loads(row["involved_characters"]) if row["involved_characters"] else [],
        objective=row["objective"],
        conflict=row["conflict"] or "",
        tone=row["tone"] or "neutral",
        status=row["status"] or "pending",
        suggested_chapter=row["suggested_chapter"],
        parallel_group=row["parallel_group"],
        foreshadows_to_plant=json.loads(row["foreshadows_to_plant"]) if row["foreshadows_to_plant"] else [],
        foreshadows_to_payoff=json.loads(row["foreshadows_to_payoff"]) if row["foreshadows_to_payoff"] else [],
    )


async def _persist_beat_result(conn, beat: SimulationBeat, result) -> None:
    """Persist scene turns and metadata from a beat simulation to DB."""
    chapter_idx = beat.suggested_chapter or 0
    scene_idx = beat.sequence

    # Save each turn with beat_id
    for turn in result.turns:
        await conn.execute(
            """INSERT INTO scene_turns
               (chapter_index, scene_index, beat_id, turn_index, character_id, turn_type,
                content, target_id, is_visible, emotional_shift, location, story_time)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                chapter_idx, scene_idx, beat.beat_id, turn.turn_index, turn.character_id,
                turn.turn_type.value if hasattr(turn.turn_type, 'value') else str(turn.turn_type),
                turn.content, turn.target_id,
                1 if turn.is_visible else 0,
                json.dumps(turn.emotional_shift) if turn.emotional_shift else '{}',
                beat.location,
                beat.story_time,
            ),
        )

    # Save scene metadata with beat_id
    opening_json = '{}'
    if result.opening_decisions:
        opening_json = json.dumps({
            cid: {
                'assessment': d.current_assessment,
                'desire': d.personal_desire,
                'approach': d.chosen_approach,
                'emotional_drive': d.emotional_drive,
            }
            for cid, d in result.opening_decisions.items()
        }, ensure_ascii=False)

    await conn.execute(
        """INSERT INTO scene_metadata
           (chapter_index, scene_index, beat_id, location, story_time, total_turns, ended_by, opening_decisions_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(chapter_index, scene_index) DO UPDATE SET
               beat_id=excluded.beat_id, total_turns=excluded.total_turns,
               ended_by=excluded.ended_by, opening_decisions_json=excluded.opening_decisions_json""",
        (chapter_idx, scene_idx, beat.beat_id, beat.location, beat.story_time,
         len(result.turns), result.ended_by, opening_json),
    )

    # Save character actions with beat_id
    for action in result.character_actions:
        await conn.execute(
            """INSERT INTO character_actions
               (character_id, chapter_index, scene_index, beat_id, action_type,
                content, target_character_id, emotional_shift)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                action.character_id, chapter_idx, scene_idx, beat.beat_id,
                action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type),
                action.content, action.target_character_id,
                json.dumps(action.emotional_shift) if action.emotional_shift else '{}',
            ),
        )

    await conn.commit()
