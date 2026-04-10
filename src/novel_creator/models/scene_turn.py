"""Scene turn models — used by SceneOrchestrator to return simulation results.

SceneResult is the output of a single scene simulation, containing all
character turns, opening decisions, and summary stats.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from novel_creator.models.memory import CharacterAction


class TurnType(str, Enum):
    """Types of character turns during scene simulation."""
    SAY = "say"
    DO = "do"
    THINK = "think"
    FEEL = "feel"
    LEAVE = "leave"


class SceneTurn(BaseModel):
    """A single character turn in a scene simulation."""
    turn_index: int = 0
    character_id: str
    turn_type: TurnType = TurnType.SAY
    content: str = ""
    target_id: str | None = None
    is_visible: bool = True
    emotional_shift: dict[str, float] = Field(default_factory=dict)
    location: str = ""
    story_time: str = ""


class OpeningDecision(BaseModel):
    """A character's opening decision at the start of a scene."""
    current_assessment: str = ""
    personal_desire: str = ""
    chosen_approach: str = ""
    emotional_drive: str = ""


class SceneResult(BaseModel):
    """Result of a scene simulation — returned by SceneOrchestrator.run()."""
    turns: list[SceneTurn] = Field(default_factory=list)
    character_actions: list[CharacterAction] = Field(default_factory=list)
    opening_decisions: dict[str, OpeningDecision] = Field(default_factory=dict)
    total_turns: int = 0
    ended_by: str = ""  # "natural" | "max_turns" | "all_left" | "error"
