"""Build the LangGraph orchestration graph."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from novel_creator.graph.edges import should_continue_chapters, should_continue_scenes
from novel_creator.graph.nodes import (
    checkpoint_save_node,
    compile_novel_node,
    director_node,
    foreshadow_check_node,
    foreshadow_plan_node,
    god_agent_node,
    reflection_node,
    simulate_scene_node,
    world_building_node,
    write_chapter_node,
)
from novel_creator.graph.state import NovelGenerationState


def build_novel_graph() -> StateGraph:
    """
    Build the V3 novel generation pipeline graph:

    START → director → world_building → foreshadow_plan → scene_router ──→ simulate_scene ──┐
                                                                    ▲                       │
                                                                    └── (more scenes?) ─────┘
                                                                    │
                                                                    └── write_chapter → foreshadow_check
                                                                                        → checkpoint_save
                                                                                        → god_agent
                                                                                        → reflection
                                                                                        → chapter_router
                                       ┌──────────────── chapter_router ──→ (more chapters?) → scene_router
                                       ├──────────────── pause → END
                                       └──────────────── compile → END
    """
    graph = StateGraph(NovelGenerationState)

    # Add nodes
    graph.add_node("director", director_node)
    graph.add_node("world_building", world_building_node)
    graph.add_node("foreshadow_plan", foreshadow_plan_node)
    graph.add_node("simulate_scene", simulate_scene_node)
    graph.add_node("write_chapter", write_chapter_node)
    graph.add_node("foreshadow_check", foreshadow_check_node)
    graph.add_node("checkpoint_save", checkpoint_save_node)
    graph.add_node("god_agent", god_agent_node)
    graph.add_node("reflection", reflection_node)
    graph.add_node("compile", compile_novel_node)

    # Entry point
    graph.set_entry_point("director")

    # Director → world building
    graph.add_edge("director", "world_building")

    # World building → foreshadow planning
    graph.add_edge("world_building", "foreshadow_plan")

    # Foreshadow plan → scene router (first scene of first chapter)
    graph.add_conditional_edges(
        "foreshadow_plan",
        should_continue_scenes,
        {
            "simulate": "simulate_scene",
            "write": "write_chapter",
            "compile": "compile",
        },
    )

    # After simulating a scene → check for more scenes or write
    graph.add_conditional_edges(
        "simulate_scene",
        should_continue_scenes,
        {
            "simulate": "simulate_scene",
            "write": "write_chapter",
            "compile": "compile",
        },
    )

    # After writing a chapter → foreshadow check
    graph.add_edge("write_chapter", "foreshadow_check")

    # After foreshadow check → checkpoint save
    graph.add_edge("foreshadow_check", "checkpoint_save")

    # After checkpoint save → god agent
    graph.add_edge("checkpoint_save", "god_agent")

    # After god agent → reflection
    graph.add_edge("god_agent", "reflection")

    # After reflection → chapter router (continue / pause / compile)
    graph.add_conditional_edges(
        "reflection",
        should_continue_chapters,
        {
            "next_chapter": "simulate_scene",
            "pause": END,
            "compile": "compile",
        },
    )

    # Compile → END
    graph.add_edge("compile", END)

    return graph


def build_resume_graph() -> StateGraph:
    """
    Build a graph for resuming from a checkpoint.

    Skips director/world_building/foreshadow_plan — starts directly at simulate_scene.
    """
    graph = StateGraph(NovelGenerationState)

    # Only the execution nodes
    graph.add_node("simulate_scene", simulate_scene_node)
    graph.add_node("write_chapter", write_chapter_node)
    graph.add_node("foreshadow_check", foreshadow_check_node)
    graph.add_node("checkpoint_save", checkpoint_save_node)
    graph.add_node("god_agent", god_agent_node)
    graph.add_node("reflection", reflection_node)
    graph.add_node("compile", compile_novel_node)

    # Entry point: scene router
    graph.set_entry_point("simulate_scene")

    # Scene loop
    graph.add_conditional_edges(
        "simulate_scene",
        should_continue_scenes,
        {
            "simulate": "simulate_scene",
            "write": "write_chapter",
            "compile": "compile",
        },
    )

    # Chapter processing chain
    graph.add_edge("write_chapter", "foreshadow_check")
    graph.add_edge("foreshadow_check", "checkpoint_save")
    graph.add_edge("checkpoint_save", "god_agent")
    graph.add_edge("god_agent", "reflection")

    graph.add_conditional_edges(
        "reflection",
        should_continue_chapters,
        {
            "next_chapter": "simulate_scene",
            "pause": END,
            "compile": "compile",
        },
    )

    graph.add_edge("compile", END)

    return graph


def compile_novel_graph():
    """Compile the graph into a runnable."""
    graph = build_novel_graph()
    return graph.compile()


def compile_resume_graph():
    """Compile the resume graph into a runnable."""
    graph = build_resume_graph()
    return graph.compile()
