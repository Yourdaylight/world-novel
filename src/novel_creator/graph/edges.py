"""Conditional edge functions for the LangGraph pipeline."""

from __future__ import annotations

from novel_creator.graph.state import NovelGenerationState


def should_continue_scenes(state: NovelGenerationState) -> str:
    """Check if there are more scenes to simulate in the current chapter."""
    chapter_idx = state["current_chapter"]
    scene_idx = state["current_scene"]
    outline = state["outline"]

    if chapter_idx >= len(outline.chapters):
        return "compile"

    chapter = outline.chapters[chapter_idx]
    if scene_idx < len(chapter.scenes):
        return "simulate"
    else:
        return "write"


def should_continue_chapters(state: NovelGenerationState) -> str:
    """Check if there are more chapters to process.

    V2: supports ``"pause"`` return value for chapter-by-chapter mode.
    """
    chapter_idx = state["current_chapter"]
    outline = state["outline"]

    if chapter_idx >= len(outline.chapters):
        return "compile"

    # V2: chapter-by-chapter mode — pause after each chapter
    mode = state.get("generation_mode", "full")
    if mode == "chapter_by_chapter" or state.get("pause_after_chapter", False):
        return "pause"

    return "next_chapter"
