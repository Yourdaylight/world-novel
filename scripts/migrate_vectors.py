#!/usr/bin/env python3
"""Migrate existing SQLite semantic_memories BLOB vectors into Qdrant.

Usage:
    python scripts/migrate_vectors.py [--db-path data/novel.db] [--qdrant-host localhost]

This reads all semantic_memories rows from SQLite, extracts the BLOB
embeddings, and upserts them into the Qdrant 'worldengine_semantic' collection.
Optionally also migrates episodic memories (generates embeddings on the fly).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


async def migrate_semantic(db_path: str, qdrant_host: str, qdrant_port: int) -> int:
    """Migrate semantic_memories BLOB embeddings to Qdrant."""
    import aiosqlite
    from novel_creator.memory.vector_store import VectorMemoryStore

    vs = VectorMemoryStore(host=qdrant_host, port=qdrant_port)
    await vs.init_collections()

    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row

    cursor = await conn.execute(
        "SELECT memory_id, character_id, content, category, importance, embedding "
        "FROM semantic_memories WHERE embedding IS NOT NULL"
    )
    rows = await cursor.fetchall()
    count = 0

    for row in rows:
        try:
            emb_bytes = row["embedding"]
            if not emb_bytes:
                continue
            embedding = np.frombuffer(emb_bytes, dtype=np.float32).tolist()
            await vs.upsert_semantic(
                memory_id=row["memory_id"],
                character_id=row["character_id"],
                content=row["content"],
                category=row["category"],
                importance=row["importance"],
                embedding=embedding,
            )
            count += 1
        except Exception as e:
            print(f"  WARN: skipped {row['memory_id']}: {e}")

    await conn.close()
    vs.close()
    return count


async def migrate_episodic(db_path: str, qdrant_host: str, qdrant_port: int) -> int:
    """Migrate episodic memories to Qdrant (generates embeddings on the fly)."""
    import aiosqlite
    from novel_creator.memory.vector_store import VectorMemoryStore

    vs = VectorMemoryStore(host=qdrant_host, port=qdrant_port)
    await vs.init_collections()

    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row

    cursor = await conn.execute(
        "SELECT memory_id, character_id, content, importance, emotional_valence, "
        "chapter_index, scene_index, heat_score "
        "FROM episodic_memories WHERE consolidated = 0"
    )
    rows = await cursor.fetchall()
    count = 0

    for row in rows:
        try:
            heat = row["heat_score"] if row["heat_score"] is not None else 0.5
            await vs.upsert_episodic(
                memory_id=row["memory_id"],
                character_id=row["character_id"],
                content=row["content"],
                importance=row["importance"],
                emotional_valence=row["emotional_valence"],
                chapter_index=row["chapter_index"],
                scene_index=row["scene_index"],
                heat_score=heat,
                embedding=None,  # Will be generated
            )
            count += 1
        except Exception as e:
            print(f"  WARN: skipped episodic {row['memory_id']}: {e}")

    await conn.close()
    vs.close()
    return count


async def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite vectors to Qdrant")
    parser.add_argument("--db-path", default="data/novel.db", help="SQLite DB path")
    parser.add_argument("--qdrant-host", default="localhost", help="Qdrant host")
    parser.add_argument("--qdrant-port", type=int, default=6333, help="Qdrant port")
    parser.add_argument("--skip-episodic", action="store_true", help="Skip episodic migration")
    args = parser.parse_args()

    if not Path(args.db_path).exists():
        print(f"ERROR: DB not found: {args.db_path}")
        sys.exit(1)

    print(f"Migrating from {args.db_path} to Qdrant at {args.qdrant_host}:{args.qdrant_port}")

    print("\n1. Migrating semantic memories...")
    sem_count = await migrate_semantic(args.db_path, args.qdrant_host, args.qdrant_port)
    print(f"   Done: {sem_count} semantic memories migrated")

    if not args.skip_episodic:
        print("\n2. Migrating episodic memories (generating embeddings)...")
        epi_count = await migrate_episodic(args.db_path, args.qdrant_host, args.qdrant_port)
        print(f"   Done: {epi_count} episodic memories migrated")

    print("\nMigration complete!")


if __name__ == "__main__":
    asyncio.run(main())
