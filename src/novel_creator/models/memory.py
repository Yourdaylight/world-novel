"""Memory and action models for character agents."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    DIALOGUE = "dialogue"
    BEHAVIOR = "behavior"
    THOUGHT = "thought"
    REACTION = "reaction"


class CharacterAction(BaseModel):
    """A single action/thought/dialogue by a character in a scene."""

    character_id: str
    chapter_index: int
    scene_index: int
    action_type: ActionType
    content: str = Field(description="行动/对话/想法的具体内容")
    target_character_id: str | None = Field(default=None, description="行动对象 (如对话目标)")
    emotional_shift: dict[str, float] = Field(default_factory=dict, description="情感变化 {维度: 变化量}")
    timestamp: datetime = Field(default_factory=datetime.now)


class EmotionalState(BaseModel):
    """Continuous emotional state for a character. Values from -1.0 to 1.0."""

    character_id: str
    happiness: float = Field(default=0.0, ge=-1.0, le=1.0)
    anger: float = Field(default=0.0, ge=-1.0, le=1.0)
    fear: float = Field(default=0.0, ge=-1.0, le=1.0)
    sadness: float = Field(default=0.0, ge=-1.0, le=1.0)
    trust: float = Field(default=0.0, ge=-1.0, le=1.0)
    surprise: float = Field(default=0.0, ge=-1.0, le=1.0)
    chapter_index: int = 0
    scene_index: int = 0

    def apply_shift(self, shift: dict[str, float]) -> "EmotionalState":
        """Apply an emotional shift and return a new clamped state."""
        data = self.model_dump()
        for dim, delta in shift.items():
            if dim in data and isinstance(data[dim], float):
                data[dim] = max(-1.0, min(1.0, data[dim] + delta))
        return EmotionalState(**data)

    def summary(self) -> str:
        dims = {
            "快乐": self.happiness, "愤怒": self.anger, "恐惧": self.fear,
            "悲伤": self.sadness, "信任": self.trust, "惊讶": self.surprise,
        }
        notable = {k: v for k, v in dims.items() if abs(v) > 0.2}
        if not notable:
            return "情绪平静"
        parts = [f"{k}({v:+.1f})" for k, v in sorted(notable.items(), key=lambda x: -abs(x[1]))]
        return "，".join(parts)


class EpisodicMemory(BaseModel):
    """A discrete episodic memory entry for a character."""

    memory_id: str = ""
    character_id: str
    chapter_index: int
    scene_index: int
    content: str = Field(description="记忆内容")
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="重要性 0-1")
    emotional_valence: float = Field(default=0.0, ge=-1.0, le=1.0, description="情感色彩")
    involved_characters: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


class SemanticMemory(BaseModel):
    """A semantic memory — beliefs, knowledge, observations."""

    memory_id: str = ""
    character_id: str
    content: str
    category: str = Field(default="observation", description="belief/knowledge/observation")
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    embedding: list[float] = Field(default_factory=list, description="向量嵌入")
