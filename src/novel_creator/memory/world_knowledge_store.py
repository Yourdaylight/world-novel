"""World knowledge store — personalized world cognition per character.

Instead of injecting the full world.summary() to every character,
each character maintains their own knowledge graph seeded from their
backstory and expanded through scene interactions.

V10: Optionally syncs knowledge entries to Neo4j graph_store.
"""

from __future__ import annotations

import asyncio
import logging

import aiosqlite

from novel_creator.models.character import CharacterProfile
from novel_creator.models.world import WorldView

logger = logging.getLogger("novel_creator.memory.graph")


class WorldKnowledgeStore:
    """Per-character world knowledge CRUD."""

    def __init__(
        self,
        conn: aiosqlite.Connection,
        character_id: str,
        *,
        graph_store=None,
    ):
        self.conn = conn
        self.character_id = character_id
        self._graph_store = graph_store

    # ------------------------------------------------------------------
    # Seed initial knowledge from character backstory
    # ------------------------------------------------------------------

    async def seed_from_backstory(
        self,
        profile: CharacterProfile,
        world_view: WorldView,
    ) -> None:
        """Initialize world knowledge based on the character's role and backstory.

        Rules:
        - 主角: birth location + basic power system common knowledge
        - 反派: own faction details + political overview
        - All: cultural notes (shared baseline)
        """
        role = (profile.role or "").lower()
        backstory = profile.backstory or ""

        # --- Cultural notes (everyone knows basics) ---
        for i, note in enumerate(world_view.cultural_notes):
            await self.learn(
                knowledge_type="culture",
                key=f"culture_{i}",
                content=note,
                source="backstory",
                confidence=0.7,
                chapter=0,
            )

        # --- Taboos and rules (common knowledge) ---
        for i, rule in enumerate(world_view.taboos_and_rules):
            await self.learn(
                knowledge_type="rule",
                key=f"rule_{i}",
                content=rule,
                source="backstory",
                confidence=0.6,
                chapter=0,
            )

        # --- Power systems: everyone knows names, but detail depends on role ---
        for ps in world_view.power_systems:
            if role in ("反派", "boss", "villain", "antagonist"):
                # Villains know power systems well
                levels_str = " → ".join(ps.levels) if ps.levels else ""
                rules_str = "；".join(ps.rules) if ps.rules else ""
                content = f"{ps.name}: {ps.description}"
                if levels_str:
                    content += f"\n等级: {levels_str}"
                if rules_str:
                    content += f"\n规则: {rules_str}"
                await self.learn("power_system", ps.name, content, "backstory", 0.8, 0)
            elif role in ("主角", "protagonist", "hero"):
                # Protagonist knows basics — common folk knowledge
                basic = f"{ps.name}: {ps.description}"
                if ps.levels:
                    # Only know first few levels
                    known_levels = ps.levels[:min(3, len(ps.levels))]
                    basic += f"\n听说过的等级: {' → '.join(known_levels)}（更高的不清楚）"
                await self.learn("power_system", ps.name, basic, "backstory", 0.4, 0)
            else:
                # Supporting characters — street-level knowledge
                await self.learn(
                    "power_system", ps.name,
                    f"听说过{ps.name}这种修炼体系",
                    "backstory", 0.3, 0,
                )

        # --- Locations: know places mentioned in backstory or home ---
        for loc in world_view.locations:
            if loc.name in backstory or any(
                keyword in backstory
                for keyword in [loc.name] + loc.connected_locations[:2]
            ):
                await self.learn(
                    "location", loc.name,
                    f"{loc.name}: {loc.description}",
                    "backstory", 0.7, 0,
                )

        # --- Factions: depends on role ---
        for fac in world_view.factions:
            if fac.name in backstory:
                # Directly connected to this faction
                content = (
                    f"{fac.name}: {fac.description}\n"
                    f"理念: {fac.ideology}\n"
                    f"领袖: {fac.leader}"
                )
                if fac.allies:
                    content += f"\n盟友: {', '.join(fac.allies)}"
                if fac.enemies:
                    content += f"\n敌对: {', '.join(fac.enemies)}"
                await self.learn("faction", fac.name, content, "backstory", 0.8, 0)
            elif role in ("反派", "boss", "villain", "antagonist"):
                # Villains know political landscape
                await self.learn(
                    "faction", fac.name,
                    f"{fac.name}: {fac.description}（领袖: {fac.leader}）",
                    "backstory", 0.6, 0,
                )
            else:
                # Others may have heard of major factions
                if fac.leader:  # Assume factions with leaders are well-known
                    await self.learn(
                        "faction", fac.name,
                        f"听说过{fac.name}这个势力",
                        "backstory", 0.3, 0,
                    )

        # --- History: only role-appropriate knowledge ---
        for hist in world_view.history:
            if hist.name in backstory or hist.era in backstory:
                await self.learn(
                    "history", hist.name,
                    f"{hist.name}: {hist.description}",
                    "backstory", 0.6, 0,
                )

    # ------------------------------------------------------------------
    # Learn new knowledge
    # ------------------------------------------------------------------

    async def learn(
        self,
        knowledge_type: str,
        key: str,
        content: str,
        source: str = "scene",
        confidence: float = 0.5,
        chapter: int = 0,
    ) -> None:
        """Add or update a piece of world knowledge."""
        await self.conn.execute(
            """INSERT INTO character_world_knowledge
               (character_id, knowledge_type, knowledge_key, content, source, confidence, chapter_learned)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(character_id, knowledge_type, knowledge_key) DO UPDATE SET
                   content = CASE WHEN excluded.confidence > character_world_knowledge.confidence
                             THEN excluded.content ELSE character_world_knowledge.content END,
                   confidence = MAX(character_world_knowledge.confidence, excluded.confidence),
                   source = excluded.source,
                   chapter_learned = excluded.chapter_learned""",
            (self.character_id, knowledge_type, key, content, source, confidence, chapter),
        )
        await self.conn.commit()

        # V10: Async sync to Neo4j (fire-and-forget)
        if self._graph_store is not None:
            try:
                asyncio.create_task(self._sync_neo4j(knowledge_type, key, content, confidence))
            except Exception as e:
                logger.warning("Neo4j knowledge sync schedule failed: %s", e)

    async def _sync_neo4j(
        self, knowledge_type: str, key: str, content: str, confidence: float,
    ) -> None:
        """Background task to sync world knowledge to Neo4j."""
        try:
            await self._graph_store.sync_world_knowledge(
                character_id=self.character_id,
                knowledge_type=knowledge_type,
                knowledge_key=key,
                content=content,
                confidence=confidence,
            )
        except Exception as e:
            logger.warning("Neo4j sync_world_knowledge failed: %s", e)

    # ------------------------------------------------------------------
    # Query knowledge
    # ------------------------------------------------------------------

    async def get_all(self) -> list[dict]:
        """Get all knowledge entries for this character."""
        cursor = await self.conn.execute(
            """SELECT knowledge_type, knowledge_key, content, source, confidence, chapter_learned
               FROM character_world_knowledge
               WHERE character_id = ?
               ORDER BY knowledge_type, confidence DESC""",
            (self.character_id,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "type": r["knowledge_type"],
                "key": r["knowledge_key"],
                "content": r["content"],
                "source": r["source"],
                "confidence": r["confidence"],
                "chapter_learned": r["chapter_learned"],
            }
            for r in rows
        ]

    async def get_knowledge_summary(self) -> str:
        """Generate a personalized world knowledge text for LLM context.

        This replaces the global world.summary() with character-specific knowledge.
        """
        entries = await self.get_all()
        if not entries:
            return ""

        parts: list[str] = []

        # Group by type
        by_type: dict[str, list[dict]] = {}
        for e in entries:
            by_type.setdefault(e["type"], []).append(e)

        type_labels = {
            "location": "了解的地点",
            "faction": "知道的势力",
            "power_system": "了解的力量体系",
            "culture": "知道的风俗",
            "rule": "知道的规则禁忌",
            "history": "听闻的历史",
        }

        for ktype, label in type_labels.items():
            items = by_type.get(ktype, [])
            if not items:
                continue
            parts.append(f"### {label}")
            for item in items:
                confidence_label = (
                    "确信" if item["confidence"] > 0.7
                    else "大概知道" if item["confidence"] > 0.4
                    else "隐约听说"
                )
                parts.append(f"- [{confidence_label}] {item['content']}")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Auto-learn from scene
    # ------------------------------------------------------------------

    async def auto_learn_from_scene(
        self,
        location: str,
        present_characters: list[str],
        world_view: WorldView,
        chapter: int = 0,
    ) -> None:
        """After a scene ends, auto-learn from the environment.

        - Visiting a new location → unlock that location's description
        - Meeting a faction member → unlock basic faction info
        """
        # Learn about the current location
        loc = world_view.get_location(location)
        if loc:
            await self.learn(
                "location", loc.name,
                f"{loc.name}: {loc.description}",
                source="scene",
                confidence=0.8,
                chapter=chapter,
            )
            # If location is controlled by a faction, learn about that faction
            if loc.controlling_faction:
                fac = world_view.get_faction(loc.controlling_faction)
                if fac:
                    await self.learn(
                        "faction", fac.name,
                        f"{fac.name}: {fac.description}",
                        source="observed",
                        confidence=0.5,
                        chapter=chapter,
                    )

        # Check if any present characters belong to known factions
        # (We look for faction mentions in character profiles)
        for cid in present_characters:
            if cid == self.character_id:
                continue
            # Load the other character's profile to check faction connections
            cursor = await self.conn.execute(
                "SELECT profile_json FROM characters WHERE character_id = ?",
                (cid,),
            )
            row = await cursor.fetchone()
            if row:
                profile_text = row["profile_json"]
                for fac in world_view.factions:
                    if fac.name in profile_text:
                        await self.learn(
                            "faction", fac.name,
                            f"{fac.name}: {fac.description}（遇到过其成员）",
                            source="observed",
                            confidence=0.4,
                            chapter=chapter,
                        )
