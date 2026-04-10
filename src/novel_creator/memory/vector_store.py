"""Qdrant-backed vector search for semantic and episodic memories.

Replaces SQLite BLOB full-table-scan cosine with HNSW index.
All operations are Optional — when Qdrant is disabled, callers
should fall back to the SQLite-based SemanticStore.search().
"""

from __future__ import annotations

import logging
from typing import Any

from novel_creator.config import settings

logger = logging.getLogger("novel_creator.memory.vector")

# Embedding dimension for bge-small-zh-v1.5
VECTOR_DIM = 512


class VectorMemoryStore:
    """Qdrant client wrapper for semantic/episodic/world_knowledge collections."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        api_key: str | None = None,
        collection_prefix: str = "worldengine",
    ):
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        self._host = host or settings.qdrant_host
        self._port = port or settings.qdrant_port
        self._api_key = api_key or settings.qdrant_api_key or None
        self._prefix = collection_prefix
        self._client = QdrantClient(
            host=self._host, port=self._port, api_key=self._api_key,
        )
        self._distance = Distance.COSINE
        self._vector_params = VectorParams(size=VECTOR_DIM, distance=self._distance)

        # Collection names
        self.semantic_collection = f"{self._prefix}_semantic"
        self.episodic_collection = f"{self._prefix}_episodic"
        self.world_knowledge_collection = f"{self._prefix}_world_knowledge"

        logger.info("VectorMemoryStore connected to %s:%d", self._host, self._port)

    async def init_collections(self) -> None:
        """Create collections if they don't exist."""
        from qdrant_client.models import VectorParams, Distance

        for name in (
            self.semantic_collection,
            self.episodic_collection,
            self.world_knowledge_collection,
        ):
            try:
                self._client.get_collection(name)
            except Exception:
                self._client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=VECTOR_DIM, distance=Distance.COSINE,
                    ),
                )
                logger.info("Created Qdrant collection: %s", name)

    # ---- Semantic Memories ----

    async def upsert_semantic(
        self,
        memory_id: str,
        character_id: str,
        content: str,
        category: str,
        importance: float,
        embedding: list[float],
        chapter_index: int = -1,
    ) -> None:
        """Upsert a semantic memory vector into Qdrant."""
        from qdrant_client.models import PointStruct

        point = PointStruct(
            id=memory_id,
            vector=embedding,
            payload={
                "character_id": character_id,
                "content": content,
                "category": category,
                "importance": importance,
                "chapter_index": chapter_index,
            },
        )
        self._client.upsert(
            collection_name=self.semantic_collection,
            points=[point],
        )

    async def search_semantic(
        self,
        character_id: str,
        query_embedding: list[float],
        top_k: int = 5,
        min_importance: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Search semantic memories by vector similarity with payload filter."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

        must_conditions = [
            FieldCondition(key="character_id", match=MatchValue(value=character_id)),
        ]
        if min_importance > 0:
            must_conditions.append(
                FieldCondition(key="importance", range=Range(gte=min_importance)),
            )

        results = self._client.search(
            collection_name=self.semantic_collection,
            query_vector=query_embedding,
            query_filter=Filter(must=must_conditions),
            limit=top_k,
        )
        return [
            {
                "memory_id": str(hit.id),
                "content": hit.payload.get("content", ""),
                "category": hit.payload.get("category", ""),
                "importance": hit.payload.get("importance", 0.5),
                "score": hit.score,
            }
            for hit in results
        ]

    # ---- Episodic Memories ----

    async def upsert_episodic(
        self,
        memory_id: str,
        character_id: str,
        content: str,
        importance: float,
        emotional_valence: float,
        chapter_index: int,
        scene_index: int,
        heat_score: float = 0.5,
        embedding: list[float] | None = None,
    ) -> None:
        """Upsert an episodic memory vector."""
        from qdrant_client.models import PointStruct

        if embedding is None:
            from novel_creator.memory.semantic_store import embed_texts
            embedding = embed_texts([content])[0]

        point = PointStruct(
            id=memory_id,
            vector=embedding,
            payload={
                "character_id": character_id,
                "content": content,
                "importance": importance,
                "emotional_valence": emotional_valence,
                "chapter_index": chapter_index,
                "scene_index": scene_index,
                "heat_score": heat_score,
            },
        )
        self._client.upsert(
            collection_name=self.episodic_collection,
            points=[point],
        )

    async def search_episodic(
        self,
        character_id: str,
        query_embedding: list[float],
        top_k: int = 5,
        min_heat: float = 0.1,
    ) -> list[dict[str, Any]]:
        """Search episodic memories by vector similarity, filtered by heat threshold."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

        results = self._client.search(
            collection_name=self.episodic_collection,
            query_vector=query_embedding,
            query_filter=Filter(must=[
                FieldCondition(key="character_id", match=MatchValue(value=character_id)),
                FieldCondition(key="heat_score", range=Range(gte=min_heat)),
            ]),
            limit=top_k,
        )
        return [
            {
                "memory_id": str(hit.id),
                "content": hit.payload.get("content", ""),
                "importance": hit.payload.get("importance", 0.5),
                "emotional_valence": hit.payload.get("emotional_valence", 0.0),
                "chapter_index": hit.payload.get("chapter_index", 0),
                "scene_index": hit.payload.get("scene_index", 0),
                "heat_score": hit.payload.get("heat_score", 0.5),
                "score": hit.score,
            }
            for hit in results
        ]

    # ---- World Knowledge ----

    async def upsert_world_knowledge(
        self,
        knowledge_id: str,
        character_id: str,
        knowledge_type: str,
        knowledge_key: str,
        content: str,
        confidence: float,
        embedding: list[float] | None = None,
    ) -> None:
        """Upsert a world knowledge entry."""
        from qdrant_client.models import PointStruct

        if embedding is None:
            from novel_creator.memory.semantic_store import embed_texts
            embedding = embed_texts([content])[0]

        point = PointStruct(
            id=knowledge_id,
            vector=embedding,
            payload={
                "character_id": character_id,
                "knowledge_type": knowledge_type,
                "knowledge_key": knowledge_key,
                "content": content,
                "confidence": confidence,
            },
        )
        self._client.upsert(
            collection_name=self.world_knowledge_collection,
            points=[point],
        )

    # ---- Utility ----

    async def update_heat_score(
        self, memory_id: str, heat_score: float,
    ) -> None:
        """Update heat_score payload for an episodic memory point."""
        self._client.set_payload(
            collection_name=self.episodic_collection,
            payload={"heat_score": heat_score},
            points=[memory_id],
        )

    async def delete_point(self, collection: str, point_id: str) -> None:
        """Delete a single point from a collection."""
        from qdrant_client.models import PointIdsList
        self._client.delete(
            collection_name=collection,
            points_selector=PointIdsList(points=[point_id]),
        )

    def close(self) -> None:
        """Close the Qdrant client connection."""
        try:
            self._client.close()
        except Exception:
            pass
