"""Core tests — character memory, emotional boundaries, context window, recall."""

import asyncio
import json

import pytest
import pytest_asyncio

from novel_creator.memory.character_memory import CharacterMemory
from novel_creator.memory.database import get_connection
from novel_creator.models.character import CharacterProfile, Goal
from novel_creator.models.memory import (
    ActionType,
    CharacterAction,
    EmotionalState,
    EpisodicMemory,
)
from novel_creator.models.relationship import Relationship
from novel_creator.models.timeline import StoryEra, StoryTimeline, TimelineEvent


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_core.db")


@pytest_asyncio.fixture
async def conn(db_path):
    c = await get_connection(db_path)
    yield c
    await c.close()


@pytest_asyncio.fixture
async def hero_memory(conn):
    """A CharacterMemory for 'hero' with a profile already saved."""
    mem = CharacterMemory(conn, "hero")
    profile = CharacterProfile(
        character_id="hero",
        name="林墨",
        age=20,
        role="主角",
        backstory="失去记忆的剑修",
        goals=[Goal(description="找到真相"), Goal(description="守护秘密", is_secret=True)],
        speaking_style="沉稳内敛",
    )
    await mem.save_profile(profile)
    # Initialize emotional state
    await mem.emotional.save_state(EmotionalState(character_id="hero"))
    return mem


# ======================================================================
# EmotionalState boundary tests
# ======================================================================

class TestEmotionalStateBoundaries:
    def test_apply_shift_clamps_to_max(self):
        """Shifting happiness above 1.0 should clamp to 1.0."""
        state = EmotionalState(character_id="hero", happiness=0.8)
        new_state = state.apply_shift({"happiness": 0.5})
        assert new_state.happiness == 1.0

    def test_apply_shift_clamps_to_min(self):
        """Shifting anger below -1.0 should clamp to -1.0."""
        state = EmotionalState(character_id="hero", anger=-0.8)
        new_state = state.apply_shift({"anger": -0.5})
        assert new_state.anger == -1.0

    def test_apply_shift_normal_range(self):
        """Normal shifts within range should work normally."""
        state = EmotionalState(character_id="hero", happiness=0.0, trust=0.5)
        new_state = state.apply_shift({"happiness": 0.3, "trust": -0.2})
        assert abs(new_state.happiness - 0.3) < 1e-9
        assert abs(new_state.trust - 0.3) < 1e-9

    def test_apply_shift_ignores_unknown_dims(self):
        """Unknown dimensions in shift dict should be ignored."""
        state = EmotionalState(character_id="hero", happiness=0.5)
        new_state = state.apply_shift({"unknown_dim": 0.5})
        assert new_state.happiness == 0.5

    def test_apply_shift_preserves_character_id(self):
        state = EmotionalState(character_id="hero", happiness=0.5)
        new_state = state.apply_shift({"happiness": 0.1})
        assert new_state.character_id == "hero"

    def test_apply_shift_at_boundary_stays(self):
        """Already at 1.0, shifting by 0 stays at 1.0."""
        state = EmotionalState(character_id="hero", happiness=1.0)
        new_state = state.apply_shift({"happiness": 0.0})
        assert new_state.happiness == 1.0

    def test_apply_shift_multiple_at_boundary(self):
        """Multiple dimensions at boundaries simultaneously."""
        state = EmotionalState(
            character_id="hero",
            happiness=0.9, anger=-0.9, fear=0.0,
        )
        new_state = state.apply_shift({
            "happiness": 0.5,   # 0.9+0.5 -> 1.0
            "anger": -0.5,      # -0.9-0.5 -> -1.0
            "fear": -0.3,       # 0.0-0.3 -> -0.3
        })
        assert new_state.happiness == 1.0
        assert new_state.anger == -1.0
        assert abs(new_state.fear - (-0.3)) < 1e-9

    def test_summary_calm_when_all_low(self):
        state = EmotionalState(character_id="hero")
        assert state.summary() == "情绪平静"

    def test_summary_shows_notable_emotions(self):
        state = EmotionalState(character_id="hero", happiness=0.8, anger=-0.5)
        summary = state.summary()
        assert "快乐" in summary
        assert "愤怒" in summary


# ======================================================================
# CharacterMemory.get_context_window tests
# ======================================================================

class TestContextWindow:
    @pytest.mark.asyncio
    async def test_context_window_with_empty_memory(self, hero_memory):
        """Context window should work with no memories, just identity."""
        ctx = await hero_memory.get_context_window(0, 0)
        assert "林墨" in ctx
        assert "主角" in ctx
        assert "失去记忆的剑修" in ctx
        assert "守护秘密" in ctx  # secret goal should appear

    @pytest.mark.asyncio
    async def test_context_window_includes_emotions(self, hero_memory):
        """Emotional state should appear in context."""
        # Set a notable emotional state
        await hero_memory.emotional.save_state(EmotionalState(
            character_id="hero", happiness=0.8, anger=-0.5,
            chapter_index=0, scene_index=0,
        ))
        ctx = await hero_memory.get_context_window(0, 0)
        assert "情感状态" in ctx

    @pytest.mark.asyncio
    async def test_context_window_includes_relationships(self, hero_memory):
        """Relationships should appear in context."""
        await hero_memory.relationships.upsert(Relationship(
            source_id="hero", target_id="villain",
            relationship_type="宿敌", trust=-0.5, affection=-0.3,
        ))
        ctx = await hero_memory.get_context_window(0, 0)
        assert "villain" in ctx
        assert "宿敌" in ctx

    @pytest.mark.asyncio
    async def test_context_window_includes_memories(self, hero_memory):
        """Recent episodic memories should appear in context."""
        await hero_memory.episodic.add(EpisodicMemory(
            character_id="hero", chapter_index=0, scene_index=0,
            content="遇到了神秘的蒙面人", importance=0.8,
        ))
        ctx = await hero_memory.get_context_window(0, 1)
        assert "蒙面人" in ctx

    @pytest.mark.asyncio
    async def test_context_window_timeline_aware(self, hero_memory):
        """With timeline, memories should be organized by era."""
        # Add memories across two eras
        await hero_memory.episodic.add(EpisodicMemory(
            character_id="hero", chapter_index=0, scene_index=0,
            content="初入江湖", importance=0.9,
        ))
        await hero_memory.episodic.add(EpisodicMemory(
            character_id="hero", chapter_index=3, scene_index=0,
            content="大战天魔", importance=0.8,
        ))

        timeline = StoryTimeline(
            eras=[
                StoryEra(
                    era_id="era_1", name="初入江湖", description="", order=0,
                    story_time_start="", story_time_end="",
                    chapter_start=0, chapter_end=2,
                ),
                StoryEra(
                    era_id="era_2", name="天魔之战", description="", order=1,
                    story_time_start="", story_time_end="",
                    chapter_start=3, chapter_end=5,
                ),
            ],
            events=[],
        )

        # Query from era 2 perspective (chapter 3)
        ctx = await hero_memory.get_context_window(3, 0, timeline=timeline)
        assert "天魔之战" in ctx or "大战天魔" in ctx
        # Past era memories should be marked as fuzzy
        if "初入江湖" in ctx:
            assert "模糊" in ctx


# ======================================================================
# CharacterMemory.recall_relevant tests
# ======================================================================

class TestRecallRelevant:
    @pytest.mark.asyncio
    async def test_recall_with_no_memories(self, hero_memory):
        """Recall should return empty list when no memories exist."""
        results = await hero_memory.recall_relevant("任何查询", 0)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_recall_returns_recent_memories(self, hero_memory):
        """Recall should include recent episodic memories."""
        await hero_memory.episodic.add(EpisodicMemory(
            character_id="hero", chapter_index=0, scene_index=0,
            content="在酒馆遇到了老人", importance=0.5,
        ))
        results = await hero_memory.recall_relevant("酒馆", 0)
        assert len(results) > 0
        assert any("酒馆" in r for r in results)

    @pytest.mark.asyncio
    async def test_recall_includes_important_memories(self, hero_memory):
        """Important memories should appear even if not recent."""
        await hero_memory.episodic.add(EpisodicMemory(
            character_id="hero", chapter_index=0, scene_index=0,
            content="发现了上古遗迹", importance=0.9,
        ))
        results = await hero_memory.recall_relevant("任何查询", 5)
        assert any("遗迹" in r for r in results)

    @pytest.mark.asyncio
    async def test_recall_deduplicates(self, hero_memory):
        """Same memory should not appear twice (recent + important overlap)."""
        await hero_memory.episodic.add(EpisodicMemory(
            character_id="hero", chapter_index=0, scene_index=0,
            content="唯一的重要记忆", importance=0.9,
        ))
        results = await hero_memory.recall_relevant("唯一", 0)
        # Count occurrences of the content
        count = sum(1 for r in results if "唯一的重要记忆" in r)
        assert count <= 1


# ======================================================================
# CharacterMemory action recording tests
# ======================================================================

class TestActionRecording:
    @pytest.mark.asyncio
    async def test_record_and_retrieve_actions(self, hero_memory):
        action = CharacterAction(
            character_id="hero",
            chapter_index=0,
            scene_index=0,
            action_type=ActionType.DIALOGUE,
            content="你是谁？",
            target_character_id="stranger",
            emotional_shift={"surprise": 0.3},
        )
        await hero_memory.record_action(action)
        actions = await hero_memory.get_actions(0, 0)
        assert len(actions) == 1
        assert actions[0].content == "你是谁？"
        assert actions[0].action_type == ActionType.DIALOGUE

    @pytest.mark.asyncio
    async def test_get_actions_filters_by_chapter(self, hero_memory):
        """Actions from different chapters should not mix."""
        for ch in range(3):
            await hero_memory.record_action(CharacterAction(
                character_id="hero", chapter_index=ch, scene_index=0,
                action_type=ActionType.BEHAVIOR, content=f"ch{ch}的行动",
            ))
        actions = await hero_memory.get_actions(1)
        assert len(actions) == 1
        assert "ch1" in actions[0].content


# ======================================================================
# Database WAL mode test
# ======================================================================

class TestDatabaseConfig:
    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self, db_path):
        """Database should be in WAL mode after connection."""
        conn = await get_connection(db_path)
        cursor = await conn.execute("PRAGMA journal_mode")
        row = await cursor.fetchone()
        assert row[0] == "wal"
        await conn.close()

    @pytest.mark.asyncio
    async def test_busy_timeout_set(self, db_path):
        """Busy timeout should be set to 30000ms."""
        conn = await get_connection(db_path)
        cursor = await conn.execute("PRAGMA busy_timeout")
        row = await cursor.fetchone()
        assert row[0] == 30000
        await conn.close()


# ======================================================================
# LLM factory tests
# ======================================================================

class TestLLMFactory:
    def test_get_llm_returns_chat_openai(self):
        from novel_creator.llm import get_llm
        llm = get_llm("director")
        assert llm is not None
        assert hasattr(llm, "model_name") or hasattr(llm, "model")

    def test_get_llm_respects_temperature_override(self):
        from novel_creator.llm import get_llm
        llm = get_llm("director", temperature=0.1)
        assert llm.temperature == 0.1

    def test_get_llm_uses_default_temperature(self):
        from novel_creator.llm import get_llm
        llm = get_llm("character")
        assert llm.temperature == 0.9  # character default

    @pytest.mark.asyncio
    async def test_invoke_with_retry_raises_after_exhaustion(self):
        """invoke_with_retry should raise after all retries are exhausted."""
        from novel_creator.llm import invoke_with_retry

        class _FailChain:
            async def ainvoke(self, input_data):
                raise ConnectionError("API down")

        with pytest.raises(ConnectionError):
            await invoke_with_retry(
                _FailChain(), {},
                max_retries=1, base_delay=0.01,
                description="test retry",
            )
