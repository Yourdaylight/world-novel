"""Tests for the memory/database layer."""

import asyncio
import os
import tempfile

import pytest
import pytest_asyncio

from novel_creator.memory.character_memory import CharacterMemory
from novel_creator.memory.database import get_connection, reset_database
from novel_creator.memory.emotional_store import EmotionalStore
from novel_creator.memory.episodic_store import EpisodicStore
from novel_creator.memory.relationship_store import RelationshipStore
from novel_creator.models.character import CharacterProfile, Goal, PersonalityTraits
from novel_creator.models.memory import (
    ActionType,
    CharacterAction,
    EmotionalState,
    EpisodicMemory,
)
from novel_creator.models.relationship import Relationship


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def conn(db_path):
    c = await get_connection(db_path)
    yield c
    await c.close()


@pytest.mark.asyncio
async def test_database_init(db_path):
    conn = await get_connection(db_path)
    cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row["name"] for row in await cursor.fetchall()]
    await conn.close()
    assert "characters" in tables
    assert "episodic_memories" in tables
    assert "emotional_states" in tables
    assert "relationships" in tables
    assert "character_actions" in tables
    assert "semantic_memories" in tables


@pytest.mark.asyncio
async def test_episodic_store(conn):
    store = EpisodicStore(conn, "hero")
    mem = EpisodicMemory(
        character_id="hero",
        chapter_index=0,
        scene_index=0,
        content="遇到了一个神秘人",
        importance=0.8,
        involved_characters=["hero", "stranger"],
    )
    mid = await store.add(mem)
    assert mid

    recent = await store.get_recent(limit=5)
    assert len(recent) == 1
    assert recent[0].content == "遇到了一个神秘人"

    important = await store.get_important(min_importance=0.7)
    assert len(important) == 1

    chapter_mems = await store.get_by_chapter(0)
    assert len(chapter_mems) == 1


@pytest.mark.asyncio
async def test_emotional_store(conn):
    store = EmotionalStore(conn, "hero")
    state = EmotionalState(
        character_id="hero",
        happiness=0.5,
        anger=-0.2,
        chapter_index=0,
        scene_index=0,
    )
    await store.save_state(state)

    latest = await store.get_latest()
    assert latest.happiness == 0.5
    assert latest.anger == -0.2

    history = await store.get_history()
    assert len(history) == 1


@pytest.mark.asyncio
async def test_relationship_store(conn):
    store = RelationshipStore(conn, "hero")
    rel = Relationship(
        source_id="hero",
        target_id="villain",
        relationship_type="敌人",
        trust=-0.7,
        affection=-0.5,
    )
    await store.upsert(rel)

    result = await store.get_with("villain")
    assert result is not None
    assert result.trust == -0.7

    # Update
    rel.trust = -0.3
    await store.upsert(rel)
    result = await store.get_with("villain")
    assert result.trust == -0.3

    all_rels = await store.get_all()
    assert len(all_rels) == 1


@pytest.mark.asyncio
async def test_character_memory_facade(conn):
    mem = CharacterMemory(conn, "hero")

    # Save profile
    profile = CharacterProfile(
        character_id="hero",
        name="李逍遥",
        role="主角",
        backstory="一个失忆少年",
        goals=[Goal(description="找回记忆")],
        speaking_style="直爽豪迈",
    )
    await mem.save_profile(profile)

    # Get profile
    loaded = await mem.get_profile()
    assert loaded.name == "李逍遥"

    # Record action
    action = CharacterAction(
        character_id="hero",
        chapter_index=0,
        scene_index=0,
        action_type=ActionType.DIALOGUE,
        content="你是谁？",
    )
    await mem.record_action(action)

    actions = await mem.get_actions(0, 0)
    assert len(actions) == 1
    assert actions[0].content == "你是谁？"

    # Save emotion
    await mem.emotional.save_state(EmotionalState(character_id="hero"))

    # Context window
    context = await mem.get_context_window(0, 0)
    assert "李逍遥" in context
    assert "主角" in context
