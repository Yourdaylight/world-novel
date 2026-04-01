"""LangGraph state definition for the novel generation pipeline."""

from __future__ import annotations

from typing import TypedDict

from novel_creator.models.character import CharacterProfile
from novel_creator.models.foreshadow import Foreshadow, PlotThread
from novel_creator.models.god import GodDecision
from novel_creator.models.memory import CharacterAction
from novel_creator.models.narrative import Chapter, NovelOutput
from novel_creator.models.relationship import RelationshipGraph
from novel_creator.models.scene_turn import SceneResult
from novel_creator.models.simulation_beat import SimulationBeat
from novel_creator.models.story import StoryOutline
from novel_creator.models.timeline import StoryTimeline
from novel_creator.models.world import WorldView


class NovelGenerationState(TypedDict, total=False):
    """State passed through the LangGraph pipeline (legacy linear graph)."""

    # User input
    genre: str
    theme: str
    premise: str
    num_chapters: int
    num_characters: int
    num_volumes: int  # V2: requested volume count

    # Director output
    outline: StoryOutline | None
    characters: list[CharacterProfile]
    relationships: RelationshipGraph | None

    # V2: World-building
    world_view: WorldView | None

    # V2: Foreshadowing
    foreshadows: list[Foreshadow]
    plot_threads: list[PlotThread]
    foreshadow_issues: list[str]

    # Chapter/scene tracking
    current_chapter: int
    current_scene: int
    character_actions: list[CharacterAction]

    # Final output
    chapters_completed: list[Chapter]
    novel: NovelOutput | None

    # Pipeline phase
    phase: str  # "directing" | "world_building" | "foreshadow_planning" |
                # "simulating" | "writing" | "reviewing" | "done"

    # Database path (for memory system)
    db_path: str

    # Progress callback
    chapter_summaries: list[str]

    # Error tracking
    error: str | None

    # V2: Generation control
    generation_mode: str          # "full" | "chapter_by_chapter"
    pause_after_chapter: bool     # Whether to pause after current chapter
    last_checkpoint_id: str | None  # Most recent checkpoint ID

    # V3: Timeline and God Agent
    timeline: StoryTimeline | None
    god_decision: GodDecision | None

    # V5: Scene transcripts for richer writer context
    scene_transcripts: list[SceneResult]


# ======================================================================
# V9: Decoupled pipeline states
# ======================================================================

class PreparationState(TypedDict, total=False):
    """State for the one-shot preparation graph.

    Runs: director -> world_building -> foreshadow_plan -> beat_plan
    All outputs are persisted to SQLite; nothing stays in memory.
    """

    # User input
    genre: str
    theme: str
    premise: str
    num_chapters: int
    num_characters: int
    num_volumes: int

    # Director output
    outline: StoryOutline | None
    characters: list[CharacterProfile]
    relationships: RelationshipGraph | None

    # World-building
    world_view: WorldView | None

    # Foreshadowing
    foreshadows: list[Foreshadow]
    plot_threads: list[PlotThread]

    # Beat plan output
    simulation_beats: list[SimulationBeat]

    # Pipeline phase
    phase: str

    # Database path
    db_path: str

    # Timeline
    timeline: StoryTimeline | None

    # Error tracking
    error: str | None


class SimulationState(TypedDict, total=False):
    """State for the continuous simulation loop graph.

    Reads/writes simulation_beats from/to SQLite.
    Runs: load_context -> pick_next_beats -> simulate_beats
          -> persist_results -> god_checkpoint -> (loop)
    """

    # Database path
    db_path: str

    # Loaded from DB each iteration
    outline: StoryOutline | None
    characters: list[CharacterProfile]
    relationships: RelationshipGraph | None
    world_view: WorldView | None
    timeline: StoryTimeline | None
    foreshadows: list[Foreshadow]
    plot_threads: list[PlotThread]

    # Current iteration
    current_beats: list[SimulationBeat]  # beats being simulated this iteration
    completed_beat_count: int            # total beats completed so far
    total_beat_count: int                # total beats in DB

    # God checkpoint tracking
    beats_since_checkpoint: int          # beats since last god_checkpoint

    # Pipeline phase
    phase: str  # "loading" | "picking" | "simulating" | "persisting" | "checkpoint" | "done"

    # Error tracking
    error: str | None

    # Control
    should_stop: bool  # external signal to stop the loop
