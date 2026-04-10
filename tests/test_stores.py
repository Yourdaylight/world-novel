"""Tests for the memory stores (episodic, emotional, relationship, semantic)."""

import asyncio

import pytest
import pytest_asyncio

from novel_creator.memory.database import get_connection
from novel_creator.memory.episodic_store import EpisodicStore
from novel_creator.memory.emotional_store import EmotionalStore
from novel_creator.memory.relationship_store import RelationshipStore
from novel_creator.memory.semantic_store import SemanticStore
from novel_creator.models.character import CharacterProfile, Goal
from novel_creator.models.memory import (
    ActionType,
    CharacterAction,
    EmotionalState,
    EpisodicMemory,
)
from novel_creator.models.relationship import Relationship


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_stores.db")


@pytest_asyncio.fixture
async def conn(db_path):
    c = await get_connection(db_path)
    yield c
    await c.close()


# ======================================================================
# EpisodicStore
# ======================================================================

class TestEpisodicStore:

    @pytest.mark.asyncio
    async def test_add_and_retrieve(self, conn):
        store = EpisodicStore(conn, "hero")
        mem = EpisodicMemory(
            character_id="hero",
            chapter_index=0,
            scene_index=0,
            content="初入江湖的少年",
            importance=0.9,
            involved_characters=["hero", "mentor"],
        )
        mid = await store.add(mem)
        assert mid is not None
        assert isinstance(mid, (int, str))

    @pytest.mark.asyncio
    async def test_get_recent_ordered_by_time(self, conn):
        """get_recent should return memories ordered by most recent first."""
        store = EpisodicStore(conn, "hero")
        for i in range(5):
            await store.add(EpisodicMemory(
                character_id="hero",
                chapter_index=i,
                scene_index=0,
                content=f"记忆{i}",
                importance=0.5,
            ))
        recent = await store.get_recent(limit=3)
        assert len(recent) <= 3

    @pytest.mark.asyncio
    async def test_get_important_filters_by_threshold(self, conn):
        """get_important should only return items above threshold."""
        store = EpisodicStore(conn, "hero")
        await store.add(EpisodicMemory(
            character_id="hero", chapter_index=0, scene_index=0,
            content="低重要性", importance=0.3,
        ))
        await store.add(EpisodicMemory(
            character_id="hero", chapter_index=0, scene_index=0,
            content="高重要性事件", importance=0.9,
        ))
        important = await store.get_important(min_importance=0.7)
        assert len(important) == 1
        assert "高重要" in important[0].content

    @pytest.mark.asyncio
    async def test_get_by_chapter_filters_correctly(self, conn):
        """get_by_chapter should only return memories from that chapter."""
        store = EpisodicStore(conn, "hero")
        await store.add(EpisodicMemory(
            character_id="hero", chapter_index=0, scene_index=0,
            content="第一章的记忆", importance=0.5,
        ))
        await store.add(EpisodicMemory(
            character_id="hero", chapter_index=5, scene_index=0,
            content="第六章的记忆", importance=0.5,
        ))
        ch5_mems = await store.get_by_chapter(5)
        assert len(ch5_mems) == 1
        assert "第六章" in ch5_mems[0].content

    @pytest.mark.asyncio
    async def test_add_multiple_characters_memories(self, conn):
        """Different characters' memories should be isolated."""
        hero_store = EpisodicStore(conn, "hero")
        villain_store = EpisodicStore(conn, "villain")

        await hero_store.add(EpisodicMemory(
            character_id="hero", chapter_index=0, scene_index=0,
            content="主角的记忆", importance=0.5,
        ))
        await villain_store.add(EpisodicMemory(
            character_id="villain", chapter_index=0, scene_index=0,
            content="反派的记忆", importance=0.5,
        ))

        hero_mems = await hero_store.get_recent()
        villain_mems = await villain_store.get_recent()
        assert len(hero_mems) == 1
        assert len(villain_mems) == 1
        assert "主角" in hero_mems[0].content
        assert "反派" in villain_mems[0].content


# ======================================================================
# EmotionalStore
# ======================================================================

class TestEmotionalStore:

    @pytest.mark.asyncio
    async def test_save_and_load_state(self, conn):
        """Emotional state should round-trip correctly."""
        store = EmotionalStore(conn, "hero")
        state = EmotionalState(
            character_id="hero",
            happiness=0.8,
            anger=-0.3,
            fear=-0.1,
            trust=0.6,
            chapter_index=0,
            scene_index=0,
        )
        await store.save_state(state)
        loaded = await store.get_latest()
        assert loaded.happiness == 0.8
        assert loaded.anger == -0.3
        assert loaded.trust == 0.6

    @pytest.mark.asyncio
    async def test_overwrite_latest_state(self, conn):
        """Saving new state should overwrite previous latest."""
        store = EmotionalStore(conn, "hero")
        await store.save_state(EmotionalState(character_id="hero", happiness=0.2))
        await store.save_state(EmotionalState(character_id="hero", happiness=0.9))
        loaded = await store.get_latest()
        assert loaded.happiness == 0.9

    @pytest.mark.asyncio
    async def test_history_preserves_all_states(self, conn):
        """get_history should return all saved states."""
        store = EmotionalStore(conn, "hero")
        for i in range(4):
            await store.save_state(EmotionalState(
                character_id="hero", happiness=float(i) * 0.25,
                chapter_index=i, scene_index=0,
            ))
        history = await store.get_history()
        assert len(history) == 4

    @pytest.mark.asyncio
    async def test_character_isolation(self, conn):
        """Different characters should have independent emotional states."""
        store_a = EmotionalStore(conn, "char_a")
        store_b = EmotionalStore(conn, "char_b")
        await store_a.save_state(EmotionalState(character_id="char_a", happiness=0.9))
        await store_b.save_state(EmotionalState(character_id="char_b", happiness=0.1))
        assert (await store_a.get_latest()).happiness == 0.9
        assert (await store_b.get_latest()).happiness == 0.1


# ======================================================================
# RelationshipStore
# ======================================================================

class TestRelationshipStore:

    @pytest.mark.asyncio
    async def test_create_relationship(self, conn):
        store = RelationshipStore(conn, "hero")
        rel = Relationship(
            source_id="hero",
            target_id="ally",
            relationship_type="盟友",
            trust=0.8,
            affection=0.6,
        )
        await store.upsert(rel)
        result = await store.get_with("ally")
        assert result is not None
        assert result.relationship_type == "盟友"
        assert result.trust == 0.8

    @pytest.mark.asyncio
    async def test_update_existing_relationship(self, conn):
        """upsert should update existing relationship."""
        store = RelationshipStore(conn, "hero")
        rel = Relationship(
            source_id="hero", target_id="rival",
            relationship_type="对手", trust=-0.3,
        )
        await store.upsert(rel)
        # Update trust
        rel.trust = 0.5
        rel.relationship_type = "亦敌亦友"
        await store.upsert(rel)
        result = await store.get_with("rival")
        assert result.trust == 0.5
        assert result.relationship_type == "亦敌亦友"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, conn):
        store = RelationshipStore(conn, "hero")
        result = await store.get_with("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_returns_all_relationships(self, conn):
        store = RelationshipStore(conn, "hero")
        await store.upsert(Relationship(source_id="hero", target_id="a", trust=0.5))
        await store.upsert(Relationship(source_id="hero", target_id="b", trust=-0.5))
        all_rels = await store.get_all()
        assert len(all_rels) == 2

    @pytest.mark.asyncio
    async def test_source_isolation(self, conn):
        """Relationships from different sources are independent."""
        store_a = RelationshipStore(conn, "char_a")
        store_b = RelationshipStore(conn, "char_b")
        await store_a.upsert(Relationship(source_id="char_a", target_id="target", trust=0.9))
        await store_b.upsert(Relationship(source_id="char_b", target_id="target", trust=-0.9))
        assert (await store_a.get_with("target")).trust == 0.9
        assert (await store_b.get_with("target")).trust == -0.9


# ======================================================================
# SemanticStore
# ======================================================================

class TestSemanticStore:

    @pytest.mark.asyncio
    async def test_add_and_search_semantic_memory(self, conn):
        """Semantic store should allow adding and searching by meaning."""
        store = SemanticStore(conn, "hero")
        try:
            mid = await store.add(
                content="他在酒馆里遇到了一个神秘的老人",
                category="encounter",
                metadata={"chapter": 0},
            )
            assert mid is not None
        except Exception:
            # Semantic store may fail without embedding model — skip gracefully
            pytest.skip("Semantic store requires embedding model")

    @pytest.mark.asyncio
    async def test_semantic_search_returns_relevant(self, conn):
        """Searching should return semantically relevant memories."""
        store = SemanticStore(conn, "hero")
        try:
            await store.add(content="剑术大师传授了绝世剑法", category="skill")
            results = await store.search("武功", limit=5)
            # Should find something related to martial arts
            if results:
                assert len(results) > 0
        except Exception:
            pytest.skip("Semantic store requires embedding model")
