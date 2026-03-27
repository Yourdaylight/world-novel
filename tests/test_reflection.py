"""Tests for the Reflection Agent — structured output, apply logic, gating."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from novel_creator.agents.reflection import (
    BeliefUpdate,
    ReflectionAgent,
    ReflectionOutput,
    SchemaUpdate,
    TraumaIdentification,
)
from novel_creator.memory.character_memory import CharacterMemory
from novel_creator.memory.database import get_connection
from novel_creator.models.character import CharacterProfile, Goal
from novel_creator.models.layered_memory import (
    CoreBelief,
    ReflectionLog,
    RelationshipSchema,
    TraumaMemory,
)
from novel_creator.models.memory import EmotionalState


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_reflection.db")


@pytest_asyncio.fixture
async def conn(db_path):
    c = await get_connection(db_path)
    yield c
    await c.close()


@pytest_asyncio.fixture
async def hero_memory(conn):
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


# ======================================================================
# ReflectionOutput model validation
# ======================================================================


class TestReflectionOutputModel:
    def test_minimal_output(self):
        output = ReflectionOutput(summary="一切平静")
        assert output.summary == "一切平静"
        assert output.belief_updates == []
        assert output.schema_updates == []
        assert output.trauma_identifications == []

    def test_full_output(self):
        output = ReflectionOutput(
            summary="这段经历让我重新审视了信任",
            belief_updates=[
                BeliefUpdate(content="信任是脆弱的", strength=0.6, is_new=True),
                BeliefUpdate(
                    content="忠诚高于一切",
                    strength=0.9,
                    is_new=False,
                    existing_belief_id="b001",
                ),
            ],
            schema_updates=[
                SchemaUpdate(
                    target_id="苏瑶",
                    mental_model="外柔内刚，值得信赖",
                    confidence=0.8,
                ),
            ],
            trauma_identifications=[
                TraumaIdentification(
                    content="目睹师父被杀的瞬间",
                    trauma_type="trauma",
                    trigger_keywords=["师父", "死亡"],
                    emotional_impact={"anger": 0.8, "sadness": 0.9},
                ),
            ],
        )
        assert len(output.belief_updates) == 2
        assert len(output.schema_updates) == 1
        assert len(output.trauma_identifications) == 1
        assert output.belief_updates[0].is_new is True
        assert output.belief_updates[1].existing_belief_id == "b001"

    def test_belief_strength_bounds(self):
        """Strength must be between 0 and 1."""
        with pytest.raises(Exception):
            BeliefUpdate(content="test", strength=1.5)
        with pytest.raises(Exception):
            BeliefUpdate(content="test", strength=-0.1)

    def test_schema_confidence_bounds(self):
        with pytest.raises(Exception):
            SchemaUpdate(target_id="x", mental_model="test", confidence=2.0)


# ======================================================================
# ReflectionAgent.reflect() — apply updates
# ======================================================================


class TestReflectionAgentApply:
    @pytest.mark.asyncio
    async def test_apply_new_belief(self, hero_memory):
        """reflect() should add new beliefs to the belief store."""
        mock_output = ReflectionOutput(
            summary="我开始相信权力会腐蚀一切",
            belief_updates=[
                BeliefUpdate(content="权力终将腐蚀一切", strength=0.7, is_new=True),
            ],
        )

        agent = ReflectionAgent()
        with patch.object(agent, "reflect", new_callable=AsyncMock) as mock_reflect:
            # Instead of mocking reflect, call _apply_updates directly
            pass

        # Directly test _apply_updates
        agent = ReflectionAgent()
        await agent._apply_updates("hero", hero_memory, 3, mock_output)

        beliefs = await hero_memory.beliefs.get_all()
        assert len(beliefs) == 1
        assert beliefs[0].content == "权力终将腐蚀一切"
        assert beliefs[0].strength == 0.7
        assert beliefs[0].origin_chapter == 3

    @pytest.mark.asyncio
    async def test_apply_strengthen_existing_belief(self, hero_memory):
        """reflect() should update strength of existing beliefs."""
        # Pre-add a belief
        bid = await hero_memory.beliefs.add(CoreBelief(
            character_id="hero",
            content="忠诚高于一切",
            strength=0.5,
            origin_chapter=1,
        ))

        mock_output = ReflectionOutput(
            summary="忠诚的信念更加坚定了",
            belief_updates=[
                BeliefUpdate(
                    content="忠诚高于一切",
                    strength=0.9,
                    is_new=False,
                    existing_belief_id=bid,
                ),
            ],
        )

        agent = ReflectionAgent()
        await agent._apply_updates("hero", hero_memory, 5, mock_output)

        beliefs = await hero_memory.beliefs.get_all()
        assert len(beliefs) == 1
        assert beliefs[0].strength == 0.9
        assert beliefs[0].last_reinforced_chapter == 5

    @pytest.mark.asyncio
    async def test_apply_schema_update(self, hero_memory):
        """reflect() should upsert relationship schemas."""
        mock_output = ReflectionOutput(
            summary="我重新认识了苏瑶",
            schema_updates=[
                SchemaUpdate(
                    target_id="苏瑶",
                    mental_model="外柔内刚，心有城府",
                    confidence=0.8,
                ),
            ],
        )

        agent = ReflectionAgent()
        await agent._apply_updates("hero", hero_memory, 4, mock_output)

        schemas = await hero_memory.schemas.get_all()
        assert len(schemas) == 1
        assert schemas[0].target_id == "苏瑶"
        assert schemas[0].mental_model == "外柔内刚，心有城府"
        assert schemas[0].confidence == 0.8

    @pytest.mark.asyncio
    async def test_apply_trauma_identification(self, hero_memory):
        """reflect() should add trauma/anchor memories."""
        mock_output = ReflectionOutput(
            summary="那一幕永远刻在心里",
            trauma_identifications=[
                TraumaIdentification(
                    content="目睹师父被杀",
                    trauma_type="trauma",
                    trigger_keywords=["师父", "死亡", "背叛"],
                    emotional_impact={"anger": 0.8, "sadness": 0.9},
                ),
            ],
        )

        agent = ReflectionAgent()
        await agent._apply_updates("hero", hero_memory, 2, mock_output)

        traumas = await hero_memory.traumas.get_all()
        assert len(traumas) == 1
        assert traumas[0].content == "目睹师父被杀"
        assert traumas[0].trauma_type == "trauma"
        assert "师父" in traumas[0].trigger_keywords

    @pytest.mark.asyncio
    async def test_apply_logs_reflection(self, hero_memory):
        """reflect() should log the reflection."""
        mock_output = ReflectionOutput(
            summary="平静的反思",
            belief_updates=[
                BeliefUpdate(content="新信念", strength=0.5, is_new=True),
            ],
            schema_updates=[
                SchemaUpdate(target_id="A", mental_model="模型A", confidence=0.5),
            ],
            trauma_identifications=[
                TraumaIdentification(content="创伤记忆", trauma_type="trauma"),
            ],
        )

        agent = ReflectionAgent()
        await agent._apply_updates("hero", hero_memory, 6, mock_output)

        last = await hero_memory.reflections.get_last_reflection()
        assert last is not None
        assert last.chapter_index == 6
        assert last.beliefs_updated == 1
        assert last.schemas_updated == 1
        assert last.traumas_identified == 1
        assert last.summary == "平静的反思"

    @pytest.mark.asyncio
    async def test_apply_empty_output(self, hero_memory):
        """Empty output should still log the reflection with zero counts."""
        mock_output = ReflectionOutput(summary="一切平静，无需改变")

        agent = ReflectionAgent()
        await agent._apply_updates("hero", hero_memory, 4, mock_output)

        last = await hero_memory.reflections.get_last_reflection()
        assert last is not None
        assert last.beliefs_updated == 0
        assert last.schemas_updated == 0
        assert last.traumas_identified == 0


# ======================================================================
# ReflectionAgent.reflect() — full flow with mocked LLM
# ======================================================================


class TestReflectionAgentFullFlow:
    @pytest.mark.asyncio
    async def test_reflect_calls_llm_and_applies(self, hero_memory):
        """Full reflect() should call LLM and apply results."""
        expected_output = ReflectionOutput(
            summary="经历让我成长了",
            belief_updates=[
                BeliefUpdate(content="坚持就是胜利", strength=0.6, is_new=True),
            ],
        )

        agent = ReflectionAgent()

        with patch("novel_creator.agents.reflection.invoke_with_retry", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = expected_output
            result = await agent.reflect("hero", hero_memory, 3)

        assert result.summary == "经历让我成长了"
        assert len(result.belief_updates) == 1

        # Verify the belief was actually added
        beliefs = await hero_memory.beliefs.get_all()
        assert len(beliefs) == 1
        assert beliefs[0].content == "坚持就是胜利"

        # Verify reflection was logged
        last = await hero_memory.reflections.get_last_reflection()
        assert last is not None
        assert last.chapter_index == 3


# ======================================================================
# should_reflect() gating
# ======================================================================


class TestShouldReflect:
    @pytest.mark.asyncio
    async def test_should_reflect_first_time(self, conn):
        """Should reflect if no prior reflections exist."""
        mem = CharacterMemory(conn, "hero")
        assert await mem.reflections.should_reflect(0) is True

    @pytest.mark.asyncio
    async def test_should_not_reflect_within_interval(self, conn):
        """Should not reflect if within interval."""
        mem = CharacterMemory(conn, "hero")
        await mem.reflections.log_reflection(ReflectionLog(
            character_id="hero",
            chapter_index=2,
            summary="第二章反思",
        ))
        assert await mem.reflections.should_reflect(2, interval=2) is False
        assert await mem.reflections.should_reflect(3, interval=2) is False

    @pytest.mark.asyncio
    async def test_should_reflect_after_interval(self, conn):
        """Should reflect once interval has passed."""
        mem = CharacterMemory(conn, "hero")
        await mem.reflections.log_reflection(ReflectionLog(
            character_id="hero",
            chapter_index=2,
            summary="第二章反思",
        ))
        assert await mem.reflections.should_reflect(4, interval=2) is True
        assert await mem.reflections.should_reflect(5, interval=2) is True

    @pytest.mark.asyncio
    async def test_should_reflect_custom_interval(self, conn):
        """Should respect custom interval values."""
        mem = CharacterMemory(conn, "hero")
        await mem.reflections.log_reflection(ReflectionLog(
            character_id="hero",
            chapter_index=0,
            summary="初始反思",
        ))
        # interval=3
        assert await mem.reflections.should_reflect(1, interval=3) is False
        assert await mem.reflections.should_reflect(2, interval=3) is False
        assert await mem.reflections.should_reflect(3, interval=3) is True
