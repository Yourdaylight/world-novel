"""Tests for the LangGraph pipeline structure."""

from novel_creator.graph.builder import build_novel_graph, compile_novel_graph
from novel_creator.graph.edges import should_continue_chapters, should_continue_scenes
from novel_creator.models.story import ChapterOutline, SceneBeat, StoryOutline


def _make_outline(n_chapters=2, n_scenes=2):
    chapters = []
    for ci in range(n_chapters):
        scenes = [
            SceneBeat(
                scene_index=si, location=f"地点{si}",
                involved_characters=["hero"], objective=f"目标{si}",
            )
            for si in range(n_scenes)
        ]
        chapters.append(ChapterOutline(
            chapter_index=ci, title=f"第{ci+1}章", summary="...", scenes=scenes,
        ))
    return StoryOutline(
        title="测试", genre="武侠", theme="成长", premise="...",
        setting="...", chapters=chapters,
    )


def test_should_continue_scenes_simulate():
    state = {
        "current_chapter": 0,
        "current_scene": 0,
        "outline": _make_outline(),
    }
    assert should_continue_scenes(state) == "simulate"


def test_should_continue_scenes_write():
    state = {
        "current_chapter": 0,
        "current_scene": 2,  # all scenes done
        "outline": _make_outline(n_scenes=2),
    }
    assert should_continue_scenes(state) == "write"


def test_should_continue_chapters_next():
    state = {
        "current_chapter": 0,
        "outline": _make_outline(n_chapters=2),
    }
    assert should_continue_chapters(state) == "next_chapter"


def test_should_continue_chapters_compile():
    state = {
        "current_chapter": 2,
        "outline": _make_outline(n_chapters=2),
    }
    assert should_continue_chapters(state) == "compile"


def test_graph_builds():
    graph = build_novel_graph()
    assert graph is not None


def test_graph_compiles():
    compiled = compile_novel_graph()
    assert compiled is not None
