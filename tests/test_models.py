"""Tests for Pydantic models."""

from novel_creator.models import (
    CharacterAction,
    CharacterProfile,
    ChapterOutline,
    EmotionalState,
    EpisodicMemory,
    Goal,
    NovelOutput,
    Chapter,
    Scene,
    PersonalityTraits,
    Relationship,
    RelationshipGraph,
    SceneBeat,
    StoryOutline,
    ActionType,
)


def test_personality_traits_defaults():
    traits = PersonalityTraits()
    assert traits.openness == 0.5
    assert traits.neuroticism == 0.5


def test_personality_traits_bounds():
    traits = PersonalityTraits(openness=0.0, conscientiousness=1.0)
    assert traits.openness == 0.0
    assert traits.conscientiousness == 1.0


def test_character_profile_serialization():
    profile = CharacterProfile(
        character_id="hero",
        name="张三",
        age=25,
        role="主角",
        backstory="一个普通的少年",
        goals=[Goal(description="找到真相"), Goal(description="保护秘密", is_secret=True)],
        speaking_style="沉稳内敛",
    )
    data = profile.model_dump()
    assert data["character_id"] == "hero"
    assert len(data["goals"]) == 2
    restored = CharacterProfile.model_validate(data)
    assert restored.name == "张三"
    assert restored.goals[1].is_secret is True


def test_emotional_state_apply_shift():
    state = EmotionalState(character_id="hero", happiness=0.5, anger=-0.3)
    new_state = state.apply_shift({"happiness": 0.3, "anger": 0.5})
    assert new_state.happiness == 0.8
    assert new_state.anger == 0.2


def test_emotional_state_clamping():
    state = EmotionalState(character_id="hero", happiness=0.9)
    new_state = state.apply_shift({"happiness": 0.5})
    assert new_state.happiness == 1.0


def test_emotional_state_summary():
    state = EmotionalState(character_id="hero", happiness=0.8, anger=-0.5)
    summary = state.summary()
    assert "快乐" in summary
    assert "愤怒" in summary


def test_emotional_state_calm():
    state = EmotionalState(character_id="hero")
    assert state.summary() == "情绪平静"


def test_relationship_graph():
    graph = RelationshipGraph()
    r1 = Relationship(source_id="hero", target_id="villain", trust=-0.5, affection=-0.8)
    graph.upsert(r1)
    assert len(graph.relationships) == 1
    assert graph.get_relationship("hero", "villain").trust == -0.5

    # Update
    r2 = Relationship(source_id="hero", target_id="villain", trust=-0.3, affection=-0.5)
    graph.upsert(r2)
    assert len(graph.relationships) == 1
    assert graph.get_relationship("hero", "villain").trust == -0.3


def test_story_outline_serialization():
    outline = StoryOutline(
        title="测试小说",
        genre="武侠",
        theme="成长",
        premise="少年闯荡江湖",
        setting="古代中国",
        chapters=[
            ChapterOutline(
                chapter_index=0,
                title="第一章",
                summary="故事开始",
                scenes=[
                    SceneBeat(scene_index=0, location="客栈", involved_characters=["hero"],
                              objective="引入主角"),
                ],
            ),
        ],
    )
    json_str = outline.model_dump_json()
    restored = StoryOutline.model_validate_json(json_str)
    assert restored.title == "测试小说"
    assert len(restored.chapters[0].scenes) == 1


def test_novel_output():
    novel = NovelOutput(
        title="测试",
        genre="武侠",
        chapters=[
            Chapter(chapter_index=0, title="开始", scenes=[
                Scene(scene_index=0, content="这是内容", pov_character="hero"),
            ]),
        ],
    )
    assert "测试" in novel.full_text
    assert novel.word_count > 0


def test_character_action():
    action = CharacterAction(
        character_id="hero",
        chapter_index=0,
        scene_index=0,
        action_type=ActionType.DIALOGUE,
        content="你好",
        target_character_id="villain",
        emotional_shift={"happiness": 0.1},
    )
    assert action.action_type == ActionType.DIALOGUE
    assert action.emotional_shift["happiness"] == 0.1
