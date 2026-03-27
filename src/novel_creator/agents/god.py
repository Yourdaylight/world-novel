"""God Agent (命运Agent) — omniscient inter-chapter decision maker."""

from __future__ import annotations

import uuid
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from novel_creator.llm import get_llm, invoke_with_retry
from novel_creator.models.god import (
    GodDecision,
    SubplotTrigger,
    TimeProgression,
    WorldEvent,
    WorldStateChange,
)
from novel_creator.models.timeline import StoryEra, StoryTimeline, TimelineEvent

GOD_PROMPT = (Path(__file__).parent.parent / "prompts" / "god.md").read_text()


class _GodDecisionOutput(BaseModel):
    """Structured output schema for the God Agent LLM call."""

    time_progression: TimeProgression | None = Field(
        default=None, description="时间推进决策 (可为空表示无时间跳跃)",
    )
    world_events: list[WorldEvent] = Field(
        default_factory=list, description="世界事件列表 (可为空)",
    )
    subplot_triggers: list[SubplotTrigger] = Field(
        default_factory=list, description="支线触发列表 (可为空)",
    )
    world_state_changes: list[WorldStateChange] = Field(
        default_factory=list, description="世界状态变化 (可为空)",
    )
    next_chapter_guidance: str = Field(
        default="", description="对下章的叙事指导",
    )


class GodAgent:
    """Omniscient inter-chapter decision maker.

    Runs between chapters to determine world events, time progression,
    subplot triggers, and narrative guidance for the next chapter.
    Uses the strongest available model (director_model) for global reasoning.
    """

    def __init__(self):
        self.llm = get_llm("god")

    async def deliberate(
        self,
        chapter_just_completed: int,
        outline,
        characters,
        world_view,
        timeline: StoryTimeline,
        chapter_summaries: list[str],
        foreshadows=None,
        plot_threads=None,
    ) -> GodDecision:
        """Make an inter-chapter decision with full omniscient context.

        Parameters
        ----------
        chapter_just_completed : int
            Index of the chapter that was just written (0-based).
        outline : StoryOutline
            The full story outline.
        characters : list[CharacterProfile]
            All characters.
        world_view : WorldView or None
            World-building data.
        timeline : StoryTimeline
            Current timeline with eras and events.
        chapter_summaries : list[str]
            Summaries of all chapters written so far.
        foreshadows : list[Foreshadow], optional
            Active foreshadows.
        plot_threads : list[PlotThread], optional
            Active plot threads.
        """
        # Build omniscient context
        omniscient_context = self._build_context(
            chapter_just_completed, outline, characters, world_view,
            timeline, chapter_summaries, foreshadows, plot_threads,
        )

        # Prepare prompt
        system_prompt = GOD_PROMPT.format(omniscient_context=omniscient_context)
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", (
                f"第{chapter_just_completed + 1}章已完成。"
                f"故事共{len(outline.chapters)}章，当前进度: "
                f"{chapter_just_completed + 1}/{len(outline.chapters)}。\n\n"
                "请以命运之神的身份，做出你的章间决策。"
            )),
        ])

        structured_llm = self.llm.with_structured_output(_GodDecisionOutput)
        chain = prompt | structured_llm
        output: _GodDecisionOutput = await invoke_with_retry(
            chain, {}, description=f"God Agent deliberation (ch{chapter_just_completed+1})",
            role="god", chapter_index=chapter_just_completed,
        )

        # Build GodDecision
        decision = GodDecision(
            decision_id=str(uuid.uuid4())[:8],
            chapter_index=chapter_just_completed,
            time_progression=output.time_progression,
            world_events=output.world_events,
            subplot_triggers=output.subplot_triggers,
            world_state_changes=output.world_state_changes,
            next_chapter_guidance=output.next_chapter_guidance,
        )

        return decision

    def _build_context(
        self,
        chapter_just_completed: int,
        outline,
        characters,
        world_view,
        timeline: StoryTimeline,
        chapter_summaries: list[str],
        foreshadows,
        plot_threads,
    ) -> str:
        """Build full omniscient context for the God Agent."""
        parts: list[str] = []

        # Story progress
        total = len(outline.chapters)
        progress_pct = round((chapter_just_completed + 1) / total * 100) if total else 0
        parts.append(f"## 故事进度\n{outline.title} ({outline.genre})")
        parts.append(f"已完成: {chapter_just_completed + 1}/{total}章 ({progress_pct}%)")
        parts.append(f"核心冲突: {outline.central_conflict}")
        parts.append(f"结局走向: {outline.resolution_direction}\n")

        # Current era
        current_era = timeline.get_current_era(chapter_just_completed)
        if current_era:
            parts.append(f"## 当前时代\n{current_era.name} ({current_era.story_time_start} — {current_era.story_time_end})")
            parts.append(f"覆盖章节: {current_era.chapter_start + 1}-{current_era.chapter_end + 1}\n")

        # Recent chapter summaries (last 3)
        if chapter_summaries:
            parts.append("## 近期章节回顾")
            for i, s in enumerate(chapter_summaries[-3:]):
                ch_idx = chapter_just_completed - len(chapter_summaries[-3:]) + i + 1
                parts.append(f"第{ch_idx + 1}章: {s[:200]}")
            parts.append("")

        # Characters overview
        parts.append("## 角色概况")
        for c in characters:
            goals_str = "; ".join(g.description for g in c.goals[:2])
            parts.append(f"- {c.name} ({c.role}): {c.backstory[:80]}... | 目标: {goals_str}")
        parts.append("")

        # World state
        if world_view:
            parts.append(f"## 世界状态\n{world_view.summary()[:500]}\n")

        # Timeline events
        if timeline.events:
            parts.append("## 已发生的重要事件")
            for ev in timeline.events[-10:]:
                parts.append(f"- [第{ev.chapter_index + 1}章] {ev.title}: {ev.description[:80]}")
            parts.append("")

        # Upcoming outline
        next_idx = chapter_just_completed + 1
        if next_idx < len(outline.chapters):
            next_ch = outline.chapters[next_idx]
            parts.append(f"## 下一章大纲\n第{next_idx + 1}章 {next_ch.title}: {next_ch.summary}")
            parts.append("")

        # Foreshadows
        if foreshadows:
            active = [f for f in foreshadows if f.status.value in ("planted", "reinforced")]
            if active:
                parts.append("## 活跃伏笔")
                for f in active[:5]:
                    parts.append(f"- {f.description} (埋设第{f.planted_chapter + 1}章, 预期第{f.expected_payoff_chapter + 1}章回收)")
                parts.append("")

        # Plot threads
        if plot_threads:
            active_threads = [pt for pt in plot_threads if pt.status == "active"]
            if active_threads:
                parts.append("## 活跃剧情线")
                for pt in active_threads[:5]:
                    parts.append(f"- {pt.name}: {pt.description[:80]}")
                parts.append("")

        return "\n".join(parts)
