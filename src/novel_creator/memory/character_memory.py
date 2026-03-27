"""Unified character memory facade — one instance per character agent."""

from __future__ import annotations

import json

import aiosqlite

from novel_creator.memory.belief_store import BeliefStore
from novel_creator.memory.emotional_store import EmotionalStore
from novel_creator.memory.episodic_store import EpisodicStore
from novel_creator.memory.reflection_store import ReflectionStore
from novel_creator.memory.relationship_store import RelationshipStore
from novel_creator.memory.schema_store import SchemaStore
from novel_creator.memory.semantic_store import SemanticStore
from novel_creator.memory.trauma_store import TraumaStore
from novel_creator.models.character import CharacterProfile
from novel_creator.models.memory import (
    CharacterAction,
    EmotionalState,
    EpisodicMemory,
    SemanticMemory,
)
from novel_creator.models.relationship import Relationship


class CharacterMemory:
    """Unified memory facade for a single character. Enforces data isolation by character_id."""

    def __init__(self, conn: aiosqlite.Connection, character_id: str):
        self.conn = conn
        self.character_id = character_id
        self.episodic = EpisodicStore(conn, character_id)
        self.emotional = EmotionalStore(conn, character_id)
        self.relationships = RelationshipStore(conn, character_id)
        self.semantic = SemanticStore(conn, character_id)
        self.beliefs = BeliefStore(conn, character_id)
        self.schemas = SchemaStore(conn, character_id)
        self.traumas = TraumaStore(conn, character_id)
        self.reflections = ReflectionStore(conn, character_id)

    async def save_profile(self, profile: CharacterProfile) -> None:
        await self.conn.execute(
            """INSERT OR REPLACE INTO characters (character_id, profile_json)
               VALUES (?, ?)""",
            (self.character_id, profile.model_dump_json()),
        )
        await self.conn.commit()

    async def get_profile(self) -> CharacterProfile | None:
        cursor = await self.conn.execute(
            "SELECT profile_json FROM characters WHERE character_id = ?",
            (self.character_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return CharacterProfile.model_validate_json(row["profile_json"])

    async def record_action(self, action: CharacterAction) -> None:
        await self.conn.execute(
            """INSERT INTO character_actions
               (character_id, chapter_index, scene_index, action_type,
                content, target_character_id, emotional_shift)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                self.character_id, action.chapter_index, action.scene_index,
                action.action_type.value, action.content,
                action.target_character_id,
                json.dumps(action.emotional_shift),
            ),
        )
        await self.conn.commit()

    async def get_actions(
        self, chapter_index: int, scene_index: int | None = None,
    ) -> list[CharacterAction]:
        if scene_index is not None:
            cursor = await self.conn.execute(
                """SELECT * FROM character_actions
                   WHERE character_id = ? AND chapter_index = ? AND scene_index = ?
                   ORDER BY id""",
                (self.character_id, chapter_index, scene_index),
            )
        else:
            cursor = await self.conn.execute(
                """SELECT * FROM character_actions
                   WHERE character_id = ? AND chapter_index = ?
                   ORDER BY scene_index, id""",
                (self.character_id, chapter_index),
            )
        rows = await cursor.fetchall()
        from novel_creator.models.memory import ActionType
        return [
            CharacterAction(
                character_id=r["character_id"],
                chapter_index=r["chapter_index"],
                scene_index=r["scene_index"],
                action_type=ActionType(r["action_type"]),
                content=r["content"],
                target_character_id=r["target_character_id"],
                emotional_shift=json.loads(r["emotional_shift"]),
            )
            for r in rows
        ]

    async def recall_relevant(
        self, query: str, chapter: int, top_k: int = 5,
    ) -> list[str]:
        """Hybrid recall: recent episodic + important + semantic similarity."""
        results: list[str] = []

        # Recent episodic memories
        recent = await self.episodic.get_recent(limit=3)
        for m in recent:
            results.append(f"[近期记忆] {m.content}")

        # Important memories
        important = await self.episodic.get_important(min_importance=0.7, limit=3)
        seen = {m.content for m in recent}
        for m in important:
            if m.content not in seen:
                results.append(f"[重要记忆] {m.content}")

        # Semantic search
        try:
            semantic_results = await self.semantic.search(query, top_k=top_k)
            for mem, score in semantic_results:
                if score > 0.3 and mem.content not in seen:
                    results.append(f"[相关记忆] {mem.content}")
        except Exception:
            pass  # Graceful degradation if embedding fails

        return results[:top_k * 2]

    async def get_context_window(
        self, chapter: int, scene: int, *, timeline=None,
    ) -> str:
        """Build a full context block for LLM prompt: identity + memories + emotion + relationships.

        Parameters
        ----------
        timeline : StoryTimeline, optional
            When provided, memories are organized by era:
            - Current era → full memories (limit=8)
            - Past eras → only important memories (importance>=0.6, limit=3, marked as "模糊")
            - World events affecting this character are included
        """
        parts: list[str] = []

        # Identity
        profile = await self.get_profile()
        if profile:
            parts.append(f"【身份】{profile.name} — {profile.role}")
            parts.append(f"  背景: {profile.backstory}")
            parts.append(f"  说话风格: {profile.speaking_style}")
            goals_str = "; ".join(g.description for g in profile.goals if not g.is_secret)
            if goals_str:
                parts.append(f"  目标: {goals_str}")
            secret_goals = [g.description for g in profile.goals if g.is_secret]
            if secret_goals:
                parts.append(f"  内心隐秘目标: {'; '.join(secret_goals)}")

        # Memories — timeline-aware or original
        if timeline and timeline.eras:
            parts.append("\n【记忆】")
            current_era = timeline.get_current_era(chapter)

            if current_era:
                # Current era → full memories
                current_memories = await self.episodic.get_by_era(
                    current_era.chapter_start, current_era.chapter_end,
                    min_importance=0.0, limit=8,
                )
                if current_memories:
                    parts.append(f"  ── {current_era.name} (当前) ──")
                    for m in current_memories:
                        parts.append(f"  [第{m.chapter_index + 1}章] {m.content}")

                # Past eras → only important, marked as fuzzy
                for era in sorted(timeline.eras, key=lambda e: e.order):
                    if era.era_id == current_era.era_id:
                        continue
                    if era.order >= current_era.order:
                        continue  # Only past eras
                    past_memories = await self.episodic.get_by_era(
                        era.chapter_start, era.chapter_end,
                        min_importance=0.6, limit=3,
                    )
                    if past_memories:
                        parts.append(f"  ── {era.name} (模糊回忆) ──")
                        for m in past_memories:
                            parts.append(f"  [模糊] {m.content}")

            # World events affecting this character
            char_events = timeline.get_events_for_character(self.character_id)
            if char_events:
                parts.append("  ── 经历的大事 ──")
                for ev in char_events[-5:]:
                    parts.append(f"  [第{ev.chapter_index + 1}章] {ev.title}: {ev.description[:60]}")
        else:
            # Original logic (backward compatible)
            memories = await self.recall_relevant(f"第{chapter}章第{scene}场景", chapter)
            if memories:
                parts.append("\n【记忆】")
                parts.extend(f"  {m}" for m in memories)

        # Emotional state
        emotion = await self.emotional.get_latest()
        parts.append(f"\n【情感状态】{emotion.summary()}")

        # Relationships
        rels = await self.relationships.get_all()
        if rels:
            parts.append("\n【人际关系】")
            for r in rels:
                other = r.target_id if r.source_id == self.character_id else r.source_id
                parts.append(f"  {other}: {r.relationship_type} (信任:{r.trust:+.1f} 好感:{r.affection:+.1f})")

        # Core beliefs
        beliefs = await self.beliefs.get_all()
        if beliefs:
            parts.append("\n【核心信念】")
            for b in beliefs:
                strength_label = "坚定" if b.strength > 0.7 else "动摇" if b.strength < 0.3 else "一般"
                parts.append(f"  [{strength_label}] {b.content}")

        # Relationship schemas (mental models)
        schemas = await self.schemas.get_all()
        if schemas:
            parts.append("\n【对他人的认知】")
            for s in schemas:
                parts.append(f"  对{s.target_id}: {s.mental_model}")

        # Trauma/anchor memories
        traumas = await self.traumas.get_all()
        if traumas:
            parts.append("\n【刻骨铭心的记忆】")
            for t in traumas:
                type_label = "🔴 创伤" if t.trauma_type == "trauma" else "🔵 锚点"
                parts.append(f"  [{type_label}] {t.content}")

        return "\n".join(parts)
