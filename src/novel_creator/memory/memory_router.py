"""Unified memory query router — routes to optimal backend per query type.

Priority:
1. Hot memories → SQLite direct (always injected)
2. Semantic search → Qdrant (with SQLite fallback)
3. Relationship paths → Neo4j (with SQLite fallback)
4. Fixed injection → SQLite (trauma, beliefs — always injected)
"""

from __future__ import annotations

import logging
from typing import Any

import aiosqlite
from pydantic import BaseModel, Field

logger = logging.getLogger("novel_creator.memory.router")


class MemoryFragment(BaseModel):
    """A single piece of recalled memory for LLM context."""

    content: str
    source: str = Field(description="hot|semantic|episodic|trauma|belief|era_summary")
    heat: float = 0.0
    similarity: float = 0.0
    memory_id: str = ""


class MemoryRouter:
    """Routes memory queries to the appropriate backend.

    When vector_store or graph_store are None, degrades gracefully
    to SQLite-only behavior.
    """

    def __init__(
        self,
        sqlite_conn: aiosqlite.Connection,
        vector_store=None,
        graph_store=None,
    ):
        self.conn = sqlite_conn
        self._vector_store = vector_store
        self._graph_store = graph_store

    async def recall_relevant(
        self,
        character_id: str,
        query: str,
        chapter: int,
        top_k: int = 8,
    ) -> list[MemoryFragment]:
        """Mixed retrieval strategy:

        1. Hot memories (heat >= 0.5) — direct injection from SQLite
        2. Semantic search — Qdrant semantic + episodic (heat 0.1–0.5 zone)
        3. Trauma/belief — fixed injection (always present)
        4. Era summaries — compressed cold memories
        5. Dedup + re-rank by heat × similarity
        """
        fragments: list[MemoryFragment] = []
        seen_ids: set[str] = set()

        # 1. Hot memories from SQLite
        try:
            cursor = await self.conn.execute(
                """SELECT memory_id, content, heat_score FROM episodic_memories
                   WHERE character_id = ? AND consolidated = 0 AND heat_score >= 0.5
                   ORDER BY heat_score DESC LIMIT ?""",
                (character_id, top_k),
            )
            rows = await cursor.fetchall()
            for r in rows:
                mid = r["memory_id"]
                if mid not in seen_ids:
                    seen_ids.add(mid)
                    fragments.append(MemoryFragment(
                        content=r["content"], source="hot",
                        heat=r["heat_score"], memory_id=mid,
                    ))
        except Exception as e:
            logger.warning("Hot memory query failed: %s", e)

        # 2. Qdrant semantic search (semantic_memories + episodic warm zone)
        if self._vector_store is not None:
            try:
                from novel_creator.memory.semantic_store import embed_texts
                query_emb = embed_texts([query])[0]

                # Semantic memories
                sem_hits = await self._vector_store.search_semantic(
                    character_id=character_id,
                    query_embedding=query_emb,
                    top_k=top_k // 2,
                )
                for h in sem_hits:
                    mid = h["memory_id"]
                    if mid not in seen_ids:
                        seen_ids.add(mid)
                        fragments.append(MemoryFragment(
                            content=h["content"], source="semantic",
                            heat=h.get("importance", 0.5),
                            similarity=h["score"], memory_id=mid,
                        ))

                # Episodic warm zone
                epi_hits = await self._vector_store.search_episodic(
                    character_id=character_id,
                    query_embedding=query_emb,
                    top_k=top_k // 2,
                    min_heat=0.1,
                )
                for h in epi_hits:
                    mid = h["memory_id"]
                    if mid not in seen_ids:
                        seen_ids.add(mid)
                        fragments.append(MemoryFragment(
                            content=h["content"], source="episodic",
                            heat=h.get("heat_score", 0.3),
                            similarity=h["score"], memory_id=mid,
                        ))
            except Exception as e:
                logger.warning("Qdrant search failed, using SQLite fallback: %s", e)
                # Fallback: SQLite semantic search
                await self._sqlite_semantic_fallback(
                    character_id, query, top_k, fragments, seen_ids,
                )
        else:
            # No Qdrant — use SQLite semantic search
            await self._sqlite_semantic_fallback(
                character_id, query, top_k, fragments, seen_ids,
            )

        # 3. Fixed injection: trauma memories
        try:
            cursor = await self.conn.execute(
                """SELECT trauma_id, content FROM trauma_memories
                   WHERE character_id = ? ORDER BY importance DESC LIMIT 3""",
                (character_id,),
            )
            for r in await cursor.fetchall():
                fragments.append(MemoryFragment(
                    content=r["content"], source="trauma",
                    heat=1.0, memory_id=r["trauma_id"],
                ))
        except Exception:
            pass

        # 4. Era summaries
        try:
            cursor = await self.conn.execute(
                """SELECT summary_id, summary, chapter_start, chapter_end
                   FROM era_summaries WHERE character_id = ?
                   ORDER BY chapter_end DESC LIMIT 3""",
                (character_id,),
            )
            for r in await cursor.fetchall():
                fragments.append(MemoryFragment(
                    content=f"[第{r['chapter_start']+1}-{r['chapter_end']+1}章] {r['summary']}",
                    source="era_summary", heat=0.05,
                    memory_id=r["summary_id"],
                ))
        except Exception:
            pass

        # 5. Re-rank: hot memories first, then by heat × similarity
        def _sort_key(f: MemoryFragment) -> float:
            if f.source in ("trauma",):
                return 10.0
            if f.source == "hot":
                return 5.0 + f.heat
            return f.heat * max(f.similarity, 0.3)

        fragments.sort(key=_sort_key, reverse=True)
        return fragments[:top_k + 4]  # Allow a few extra for trauma/era

    async def _sqlite_semantic_fallback(
        self,
        character_id: str,
        query: str,
        top_k: int,
        fragments: list[MemoryFragment],
        seen_ids: set[str],
    ) -> None:
        """SQLite-based semantic search fallback (full-table-scan cosine)."""
        try:
            import numpy as np
            from novel_creator.memory.semantic_store import (
                embed_texts, cosine_similarity,
            )

            query_emb = np.array(embed_texts([query])[0], dtype=np.float32)
            cursor = await self.conn.execute(
                "SELECT * FROM semantic_memories WHERE character_id = ?",
                (character_id,),
            )
            rows = await cursor.fetchall()
            scored = []
            for row in rows:
                stored = np.frombuffer(row["embedding"], dtype=np.float32)
                score = cosine_similarity(query_emb, stored)
                scored.append((row, score))
            scored.sort(key=lambda x: x[1], reverse=True)
            for row, score in scored[:top_k]:
                mid = row["memory_id"]
                if mid not in seen_ids and score > 0.3:
                    seen_ids.add(mid)
                    fragments.append(MemoryFragment(
                        content=row["content"], source="semantic",
                        heat=row["importance"], similarity=score,
                        memory_id=mid,
                    ))
        except Exception as e:
            logger.warning("SQLite semantic fallback failed: %s", e)

    async def get_relationship_context(
        self,
        character_id: str,
        present_characters: list[str],
    ) -> str:
        """Get relationship context, preferring Neo4j for rich graph queries.

        Falls back to SQLite if Neo4j is unavailable.
        """
        # Try Neo4j first
        if self._graph_store is not None:
            try:
                context = await self._graph_store.get_social_context(character_id)
                if context:
                    return context
            except Exception as e:
                logger.warning("Neo4j social context failed: %s", e)

        # Fallback: SQLite relationships
        try:
            cursor = await self.conn.execute(
                """SELECT * FROM relationships
                   WHERE source_id = ? OR target_id = ?""",
                (character_id, character_id),
            )
            rows = await cursor.fetchall()
            if not rows:
                return ""
            parts = []
            for r in rows:
                other = r["target_id"] if r["source_id"] == character_id else r["source_id"]
                parts.append(
                    f"{other}: {r['relationship_type']} "
                    f"(信任:{r['trust']:+.1f} 好感:{r['affection']:+.1f})"
                )
            return "\n".join(parts)
        except Exception:
            return ""
