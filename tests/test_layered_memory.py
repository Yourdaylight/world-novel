"""Tests for the layered memory system — beliefs, schemas, trauma, reflection."""

import pytest
import pytest_asyncio

from novel_creator.memory.belief_store import BeliefStore
from novel_creator.memory.character_memory import CharacterMemory
from novel_creator.memory.database import get_connection
from novel_creator.memory.reflection_store import ReflectionStore
from novel_creator.memory.schema_store import SchemaStore
from novel_creator.memory.trauma_store import TraumaStore
from novel_creator.models.character import CharacterProfile, Goal
from novel_creator.models.layered_memory import (
    CoreBelief,
    ReflectionLog,
    RelationshipSchema,
    TraumaMemory,
)
from novel_creator.models.memory import EmotionalState


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_layered.db")


@pytest_asyncio.fixture
async def conn(db_path):
    c = await get_connection(db_path)
    yield c
    await c.close()


# ======================================================================
# BeliefStore tests
# ======================================================================


class TestBeliefStore:
    @pytest.mark.asyncio
    async def test_add_and_get_all(self, conn):
        store = BeliefStore(conn, "hero")
        bid = await store.add(CoreBelief(
            character_id="hero",
            content="权力终将腐蚀一切",
            strength=0.8,
            origin_chapter=1,
        ))
        assert bid

        beliefs = await store.get_all()
        assert len(beliefs) == 1
        assert beliefs[0].content == "权力终将腐蚀一切"
        assert beliefs[0].strength == 0.8

    @pytest.mark.asyncio
    async def test_update_strength(self, conn):
        store = BeliefStore(conn, "hero")
        bid = await store.add(CoreBelief(
            character_id="hero",
            content="忠诚高于一切",
            strength=0.5,
        ))
        await store.update_strength(bid, 0.9, chapter=3)

        beliefs = await store.get_all()
        assert beliefs[0].strength == 0.9
        assert beliefs[0].last_reinforced_chapter == 3

    @pytest.mark.asyncio
    async def test_update_strength_clamps(self, conn):
        store = BeliefStore(conn, "hero")
        bid = await store.add(CoreBelief(
            character_id="hero",
            content="信念",
            strength=0.5,
        ))
        await store.update_strength(bid, 1.5, chapter=1)
        beliefs = await store.get_all()
        assert beliefs[0].strength == 1.0

        await store.update_strength(bid, -0.5, chapter=2)
        beliefs = await store.get_all()
        assert beliefs[0].strength == 0.0

    @pytest.mark.asyncio
    async def test_get_relevant(self, conn):
        store = BeliefStore(conn, "hero")
        await store.add(CoreBelief(character_id="hero", content="权力终将腐蚀一切"))
        await store.add(CoreBelief(character_id="hero", content="忠诚高于一切"))
        await store.add(CoreBelief(character_id="hero", content="强者为尊"))

        results = await store.get_relevant(["权力", "忠诚"])
        assert len(results) == 2
        contents = {b.content for b in results}
        assert "权力终将腐蚀一切" in contents
        assert "忠诚高于一切" in contents


# ======================================================================
# SchemaStore tests
# ======================================================================


class TestSchemaStore:
    @pytest.mark.asyncio
    async def test_upsert_and_get_for_target(self, conn):
        store = SchemaStore(conn, "hero")
        await store.upsert(RelationshipSchema(
            character_id="hero",
            target_id="苏瑶",
            mental_model="看似柔弱实则坚强",
            confidence=0.7,
        ))

        schema = await store.get_for_target("苏瑶")
        assert schema is not None
        assert schema.mental_model == "看似柔弱实则坚强"
        assert schema.confidence == 0.7

    @pytest.mark.asyncio
    async def test_upsert_replaces_existing(self, conn):
        store = SchemaStore(conn, "hero")
        await store.upsert(RelationshipSchema(
            character_id="hero",
            target_id="苏瑶",
            mental_model="看似柔弱实则坚强",
            confidence=0.5,
        ))
        await store.upsert(RelationshipSchema(
            character_id="hero",
            target_id="苏瑶",
            mental_model="外柔内刚，心机深沉",
            confidence=0.9,
            last_updated_chapter=5,
        ))

        schemas = await store.get_all()
        assert len(schemas) == 1
        assert schemas[0].mental_model == "外柔内刚，心机深沉"
        assert schemas[0].confidence == 0.9

    @pytest.mark.asyncio
    async def test_get_for_target_returns_none(self, conn):
        store = SchemaStore(conn, "hero")
        result = await store.get_for_target("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all(self, conn):
        store = SchemaStore(conn, "hero")
        await store.upsert(RelationshipSchema(
            character_id="hero", target_id="A", mental_model="model_a",
        ))
        await store.upsert(RelationshipSchema(
            character_id="hero", target_id="B", mental_model="model_b",
        ))

        schemas = await store.get_all()
        assert len(schemas) == 2


# ======================================================================
# TraumaStore tests
# ======================================================================


class TestTraumaStore:
    @pytest.mark.asyncio
    async def test_add_and_get_all(self, conn):
        store = TraumaStore(conn, "hero")
        tid = await store.add(TraumaMemory(
            character_id="hero",
            content="目睹师父被杀",
            trauma_type="trauma",
            trigger_keywords=["师父", "死亡", "背叛"],
            emotional_impact={"anger": 0.8, "sadness": 0.9},
            origin_chapter=1,
        ))
        assert tid

        traumas = await store.get_all()
        assert len(traumas) == 1
        assert traumas[0].content == "目睹师父被杀"
        assert traumas[0].trauma_type == "trauma"
        assert "师父" in traumas[0].trigger_keywords

    @pytest.mark.asyncio
    async def test_get_triggered_by(self, conn):
        store = TraumaStore(conn, "hero")
        await store.add(TraumaMemory(
            character_id="hero",
            content="目睹师父被杀",
            trigger_keywords=["师父", "死亡", "背叛"],
        ))
        await store.add(TraumaMemory(
            character_id="hero",
            content="童年在山间修炼的美好时光",
            trauma_type="anchor",
            trigger_keywords=["山间", "修炼", "童年"],
        ))

        # Should match first trauma
        results = await store.get_triggered_by(["背叛", "阴谋"])
        assert len(results) == 1
        assert results[0].content == "目睹师父被杀"

        # Should match second
        results = await store.get_triggered_by(["修炼"])
        assert len(results) == 1
        assert results[0].trauma_type == "anchor"

        # No match
        results = await store.get_triggered_by(["无关词"])
        assert len(results) == 0


# ======================================================================
# ReflectionStore tests
# ======================================================================


class TestReflectionStore:
    @pytest.mark.asyncio
    async def test_log_and_get_last(self, conn):
        store = ReflectionStore(conn, "hero")
        rid = await store.log_reflection(ReflectionLog(
            character_id="hero",
            chapter_index=2,
            beliefs_updated=1,
            schemas_updated=2,
            traumas_identified=0,
            summary="第二章反思：对忠诚的信念增强",
        ))
        assert rid

        last = await store.get_last_reflection()
        assert last is not None
        assert last.chapter_index == 2
        assert last.beliefs_updated == 1
        assert "忠诚" in last.summary

    @pytest.mark.asyncio
    async def test_should_reflect_no_prior(self, conn):
        store = ReflectionStore(conn, "hero")
        assert await store.should_reflect(0) is True

    @pytest.mark.asyncio
    async def test_should_reflect_within_interval(self, conn):
        store = ReflectionStore(conn, "hero")
        await store.log_reflection(ReflectionLog(
            character_id="hero", chapter_index=3,
        ))
        # Same chapter — should not reflect
        assert await store.should_reflect(3, interval=2) is False
        # 1 chapter later — still within interval
        assert await store.should_reflect(4, interval=2) is False
        # 2 chapters later — should reflect
        assert await store.should_reflect(5, interval=2) is True

    @pytest.mark.asyncio
    async def test_get_last_returns_none_when_empty(self, conn):
        store = ReflectionStore(conn, "hero")
        assert await store.get_last_reflection() is None


# ======================================================================
# CharacterMemory context window integration
# ======================================================================


class TestContextWindowLayeredMemory:
    @pytest_asyncio.fixture
    async def hero_memory(self, conn):
        mem = CharacterMemory(conn, "hero")
        profile = CharacterProfile(
            character_id="hero",
            name="林墨",
            age=20,
            role="主角",
            backstory="失去记忆的剑修",
            goals=[Goal(description="找到真相")],
            speaking_style="沉稳内敛",
        )
        await mem.save_profile(profile)
        await mem.emotional.save_state(EmotionalState(character_id="hero"))
        return mem

    @pytest.mark.asyncio
    async def test_context_includes_beliefs(self, hero_memory):
        await hero_memory.beliefs.add(CoreBelief(
            character_id="hero",
            content="权力终将腐蚀一切",
            strength=0.9,
        ))
        ctx = await hero_memory.get_context_window(0, 0)
        assert "核心信念" in ctx
        assert "权力终将腐蚀一切" in ctx
        assert "坚定" in ctx

    @pytest.mark.asyncio
    async def test_context_includes_schemas(self, hero_memory):
        await hero_memory.schemas.upsert(RelationshipSchema(
            character_id="hero",
            target_id="苏瑶",
            mental_model="看似柔弱实则坚强",
        ))
        ctx = await hero_memory.get_context_window(0, 0)
        assert "对他人的认知" in ctx
        assert "苏瑶" in ctx
        assert "看似柔弱实则坚强" in ctx

    @pytest.mark.asyncio
    async def test_context_includes_traumas(self, hero_memory):
        await hero_memory.traumas.add(TraumaMemory(
            character_id="hero",
            content="目睹师父被杀",
            trauma_type="trauma",
        ))
        ctx = await hero_memory.get_context_window(0, 0)
        assert "刻骨铭心的记忆" in ctx
        assert "目睹师父被杀" in ctx
        assert "创伤" in ctx

    @pytest.mark.asyncio
    async def test_context_omits_empty_layers(self, hero_memory):
        """When no beliefs/schemas/traumas, those sections should not appear."""
        ctx = await hero_memory.get_context_window(0, 0)
        assert "核心信念" not in ctx
        assert "对他人的认知" not in ctx
        assert "刻骨铭心的记忆" not in ctx
