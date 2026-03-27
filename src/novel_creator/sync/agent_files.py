"""AgentFileSync — bidirectional sync between DB and agent markdown files.

Each character gets:
    agents/{character_id}/agent.md   ← 角色档案 (= LLM system prompt)
    agents/{character_id}/soul.md    ← 深层人格/价值观/底线
    agents/{character_id}/memories/  ← 按时代归档的长期记忆

The God Agent gets:
    agents/god/agent.md              ← 命运Agent prompt
    agents/god/timeline.md           ← 主时间线
"""

from __future__ import annotations

import json
from pathlib import Path

import aiosqlite

from novel_creator.memory.character_memory import CharacterMemory
from novel_creator.models.character import CharacterProfile
from novel_creator.models.timeline import StoryTimeline


class AgentFileSync:
    """Bidirectional sync between DB and agent markdown files."""

    def __init__(self, novel_dir: Path):
        self.novel_dir = novel_dir
        self.agents_dir = novel_dir / "agents"

    # ── DB → 文件 (导出) ──────────────────────────────────────────

    async def export_character(
        self,
        conn: aiosqlite.Connection,
        character_id: str,
        timeline: StoryTimeline | None = None,
    ) -> Path:
        """Export a character's agent.md, soul.md, and memories/ from DB."""
        char_dir = self.agents_dir / character_id
        char_dir.mkdir(parents=True, exist_ok=True)

        mem = CharacterMemory(conn, character_id)
        profile = await mem.get_profile()
        if profile is None:
            return char_dir

        # ── agent.md ──
        agent_md = self._render_agent_md(profile)
        (char_dir / "agent.md").write_text(agent_md, encoding="utf-8")

        # ── soul.md ──
        soul_md = self._render_soul_md(profile)
        (char_dir / "soul.md").write_text(soul_md, encoding="utf-8")

        # ── memories/ ──
        if timeline and timeline.eras:
            memories_dir = char_dir / "memories"
            memories_dir.mkdir(exist_ok=True)
            await self._export_memories(conn, character_id, timeline, memories_dir)

        return char_dir

    async def export_god_agent(
        self,
        conn: aiosqlite.Connection,
        timeline: StoryTimeline,
    ) -> Path:
        """Export god/agent.md and god/timeline.md."""
        god_dir = self.agents_dir / "god"
        god_dir.mkdir(parents=True, exist_ok=True)

        # ── agent.md (God prompt reference) ──
        god_prompt_path = Path(__file__).parent.parent / "prompts" / "god.md"
        if god_prompt_path.exists():
            god_md = god_prompt_path.read_text(encoding="utf-8")
        else:
            god_md = "# 命运之神\n\n> 上帝视角的故事掌控者\n"
        (god_dir / "agent.md").write_text(god_md, encoding="utf-8")

        # ── timeline.md ──
        timeline_md = self._render_timeline_md(timeline)
        (god_dir / "timeline.md").write_text(timeline_md, encoding="utf-8")

        # ── Export god decisions ──
        from novel_creator.memory import timeline_store
        decisions = await timeline_store.get_god_decisions(conn)
        if decisions:
            decisions_md = "# 命运决策历史\n\n"
            for d in decisions:
                decisions_md += f"## 第{d.chapter_index + 1}章后 ({d.decision_id})\n"
                decisions_md += d.summary() + "\n\n"
            (god_dir / "decisions.md").write_text(decisions_md, encoding="utf-8")

        return god_dir

    async def export_all(
        self,
        conn: aiosqlite.Connection,
        timeline: StoryTimeline | None = None,
    ) -> None:
        """Export all characters and the god agent."""
        # Get all character IDs
        cursor = await conn.execute("SELECT character_id FROM characters")
        rows = await cursor.fetchall()

        for row in rows:
            await self.export_character(conn, row["character_id"], timeline)

        if timeline:
            await self.export_god_agent(conn, timeline)

    # ── 文件 → DB (导入人类编辑) ──────────────────────────────────

    async def import_character(
        self,
        conn: aiosqlite.Connection,
        character_id: str,
    ) -> bool:
        """Import human edits from agent.md/soul.md back into DB.

        Currently imports core_values from soul.md back into CharacterProfile.
        Returns True if changes were made.
        """
        char_dir = self.agents_dir / character_id
        if not char_dir.exists():
            return False

        mem = CharacterMemory(conn, character_id)
        profile = await mem.get_profile()
        if profile is None:
            return False

        changed = False

        # Import soul.md → core_values
        soul_path = char_dir / "soul.md"
        if soul_path.exists():
            soul_text = soul_path.read_text(encoding="utf-8")
            new_values = self._parse_soul_values(soul_text)
            if new_values and new_values != profile.core_values:
                profile.core_values = new_values
                changed = True

        if changed:
            await mem.save_profile(profile)

        return changed

    async def import_all(self, conn: aiosqlite.Connection) -> int:
        """Import all character edits. Returns count of changed characters."""
        if not self.agents_dir.exists():
            return 0
        count = 0
        for char_dir in self.agents_dir.iterdir():
            if char_dir.is_dir() and char_dir.name != "god":
                if await self.import_character(conn, char_dir.name):
                    count += 1
        return count

    # ── 渲染模板 ──────────────────────────────────────────────────

    def _render_agent_md(self, profile: CharacterProfile) -> str:
        """Render agent.md — character profile as LLM system prompt."""
        p = profile.personality
        goals_public = [g for g in profile.goals if not g.is_secret]
        goals_secret = [g for g in profile.goals if g.is_secret]

        md = f"# {profile.name}\n\n"
        md += f"> {profile.role} | {profile.age}岁"
        if profile.gender:
            md += f" | {profile.gender}"
        md += "\n\n"

        md += f"## 身份背景\n{profile.backstory}\n\n"

        if profile.appearance:
            md += f"## 外貌\n{profile.appearance}\n\n"

        md += f"## 说话风格\n{profile.speaking_style}\n\n"

        md += "## 性格特质 (大五人格)\n"
        md += f"- 开放性: {p.openness:.1f}\n"
        md += f"- 尽责性: {p.conscientiousness:.1f}\n"
        md += f"- 外向性: {p.extraversion:.1f}\n"
        md += f"- 宜人性: {p.agreeableness:.1f}\n"
        md += f"- 神经质: {p.neuroticism:.1f}\n\n"

        if goals_public:
            md += "## 目标\n### 公开目标\n"
            for g in goals_public:
                md += f"- {g.description}\n"
            md += "\n"

        if goals_secret:
            md += "### 秘密目标\n"
            for g in goals_secret:
                md += f"- {g.description}\n"
            md += "\n"

        if profile.quirks:
            md += "## 特点/癖好\n"
            for q in profile.quirks:
                md += f"- {q}\n"
            md += "\n"

        return md

    def _render_soul_md(self, profile: CharacterProfile) -> str:
        """Render soul.md — deep personality values."""
        md = f"# {profile.name} — 灵魂深处\n\n"

        md += "## 核心价值观\n"
        if profile.core_values:
            for v in profile.core_values:
                md += f"- {v}\n"
        else:
            md += "- (待定义)\n"
        md += "\n"

        md += "## 内心信念\n"
        md += "> 驱动一切决定的信念，极端压力下也不会改变。\n\n"
        md += "(可由用户在此编辑)\n\n"

        md += "## 内心矛盾\n"
        md += "> 未解决的深层挣扎。\n\n"
        md += "(可由用户在此编辑)\n\n"

        md += "## 底线\n"
        md += "> 绝对不会做的事；什么情况下会打破底线。\n\n"
        md += "(可由用户在此编辑)\n"

        return md

    async def _export_memories(
        self,
        conn: aiosqlite.Connection,
        character_id: str,
        timeline: StoryTimeline,
        memories_dir: Path,
    ) -> None:
        """Export episodic memories grouped by era."""
        from novel_creator.memory.episodic_store import EpisodicStore
        store = EpisodicStore(conn, character_id)

        for era in timeline.eras:
            # Get memories for this era's chapter range
            memories = await store.get_by_era(
                era.chapter_start, era.chapter_end, min_importance=0.0, limit=50,
            )
            if not memories:
                continue

            era_file = memories_dir / f"{era.era_id}.md"
            md = f"# {era.name}\n"
            md += f"> {era.story_time_start} — {era.story_time_end}\n\n"

            for m in memories:
                marker = "⭐" if m.importance >= 0.7 else "·"
                md += f"{marker} [第{m.chapter_index + 1}章] {m.content}\n"

            era_file.write_text(md, encoding="utf-8")

    def _render_timeline_md(self, timeline: StoryTimeline) -> str:
        """Render the main timeline as markdown."""
        md = "# 主时间线\n\n"

        if not timeline.eras:
            md += "(暂无时代划分)\n"
            return md

        for era in sorted(timeline.eras, key=lambda e: e.order):
            md += f"## {era.name}\n"
            md += f"> {era.story_time_start} — {era.story_time_end}\n"
            md += f"> 章节 {era.chapter_start + 1}-{era.chapter_end + 1}\n\n"

            era_events = timeline.get_events_in_era(era.era_id)
            if era_events:
                for ev in sorted(era_events, key=lambda e: e.chapter_index):
                    importance_marker = "⭐" if ev.importance >= 0.7 else "·"
                    source_tag = f" [{ev.source}]" if ev.source != "director" else ""
                    md += f"{importance_marker} [第{ev.chapter_index + 1}章] "
                    md += f"**{ev.title}**{source_tag}\n"
                    md += f"  {ev.description}\n"
                    if ev.affected_characters:
                        md += f"  影响角色: {', '.join(ev.affected_characters)}\n"
                    md += "\n"
            else:
                md += "(暂无事件)\n\n"

        return md

    def _parse_soul_values(self, soul_text: str) -> list[str]:
        """Parse core values from soul.md text."""
        values: list[str] = []
        in_values_section = False
        for line in soul_text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("## 核心价值观"):
                in_values_section = True
                continue
            if stripped.startswith("## ") and in_values_section:
                break
            if in_values_section and stripped.startswith("- "):
                val = stripped[2:].strip()
                if val and val != "(待定义)":
                    values.append(val)
        return values
