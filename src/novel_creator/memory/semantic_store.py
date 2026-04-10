"""Semantic memory store with vector embeddings and cosine similarity search.

V10: When a VectorMemoryStore (Qdrant) is available, search() routes to
Qdrant HNSW for O(logN) retrieval. add() dual-writes to both SQLite and Qdrant.
Falls back to SQLite full-table-scan cosine when Qdrant is disabled.
"""

from __future__ import annotations

import logging
import uuid

import aiosqlite
import numpy as np

from novel_creator.models.memory import SemanticMemory

logger = logging.getLogger("novel_creator.memory.vector")

# Lazy-loaded embedding model
_embed_model = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from fastembed import TextEmbedding
        from novel_creator.config import settings
        _embed_model = TextEmbedding(model_name=settings.embedding_model)
    return _embed_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using the configured model."""
    model = _get_embed_model()
    embeddings = list(model.embed(texts))
    return [e.tolist() for e in embeddings]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class SemanticStore:
    def __init__(
        self,
        conn: aiosqlite.Connection,
        character_id: str,
        *,
        vector_store=None,
    ):
        self.conn = conn
        self.character_id = character_id
        self._vector_store = vector_store

    async def add(self, memory: SemanticMemory) -> str:
        memory_id = memory.memory_id or str(uuid.uuid4())
        # Generate embedding if not provided
        if not memory.embedding:
            embeddings = embed_texts([memory.content])
            memory.embedding = embeddings[0]
        embedding_bytes = np.array(memory.embedding, dtype=np.float32).tobytes()
        await self.conn.execute(
            """INSERT INTO semantic_memories
               (memory_id, character_id, content, category, importance, embedding)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (memory_id, self.character_id, memory.content,
             memory.category, memory.importance, embedding_bytes),
        )
        await self.conn.commit()

        # V10: Dual-write to Qdrant
        if self._vector_store is not None:
            try:
                await self._vector_store.upsert_semantic(
                    memory_id=memory_id,
                    character_id=self.character_id,
                    content=memory.content,
                    category=memory.category,
                    importance=memory.importance,
                    embedding=memory.embedding,
                )
            except Exception as e:
                logger.warning("Qdrant upsert_semantic failed: %s", e)

        return memory_id

    async def search(self, query: str, top_k: int = 5) -> list[tuple[SemanticMemory, float]]:
        """Search for semantically similar memories.

        V10: Routes to Qdrant HNSW when available, falls back to SQLite full-scan.
        """
        query_embedding_list = embed_texts([query])[0]

        # Try Qdrant first
        if self._vector_store is not None:
            try:
                hits = await self._vector_store.search_semantic(
                    character_id=self.character_id,
                    query_embedding=query_embedding_list,
                    top_k=top_k,
                )
                return [
                    (
                        SemanticMemory(
                            memory_id=h["memory_id"],
                            character_id=self.character_id,
                            content=h["content"],
                            category=h["category"],
                            importance=h["importance"],
                        ),
                        h["score"],
                    )
                    for h in hits
                ]
            except Exception as e:
                logger.warning("Qdrant search_semantic failed, falling back to SQLite: %s", e)

        # Fallback: SQLite full-table-scan cosine
        query_embedding = np.array(query_embedding_list, dtype=np.float32)
        cursor = await self.conn.execute(
            """SELECT * FROM semantic_memories WHERE character_id = ?""",
            (self.character_id,),
        )
        rows = await cursor.fetchall()
        results: list[tuple[SemanticMemory, float]] = []
        for row in rows:
            stored_emb = np.frombuffer(row["embedding"], dtype=np.float32)
            score = cosine_similarity(query_embedding, stored_emb)
            mem = SemanticMemory(
                memory_id=row["memory_id"],
                character_id=row["character_id"],
                content=row["content"],
                category=row["category"],
                importance=row["importance"],
            )
            results.append((mem, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    async def get_all(self) -> list[SemanticMemory]:
        cursor = await self.conn.execute(
            """SELECT memory_id, character_id, content, category, importance
               FROM semantic_memories WHERE character_id = ?""",
            (self.character_id,),
        )
        rows = await cursor.fetchall()
        return [
            SemanticMemory(
                memory_id=r["memory_id"], character_id=r["character_id"],
                content=r["content"], category=r["category"],
                importance=r["importance"],
            )
            for r in rows
        ]
