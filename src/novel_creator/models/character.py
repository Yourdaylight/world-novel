"""Character profile and personality models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PersonalityTraits(BaseModel):
    """Big Five personality traits, each 0.0-1.0."""

    openness: float = Field(default=0.5, ge=0.0, le=1.0, description="开放性")
    conscientiousness: float = Field(default=0.5, ge=0.0, le=1.0, description="尽责性")
    extraversion: float = Field(default=0.5, ge=0.0, le=1.0, description="外向性")
    agreeableness: float = Field(default=0.5, ge=0.0, le=1.0, description="宜人性")
    neuroticism: float = Field(default=0.5, ge=0.0, le=1.0, description="神经质")


class Goal(BaseModel):
    """A character's goal — may be public or secret."""

    description: str = Field(description="目标描述")
    is_secret: bool = Field(default=False, description="是否为秘密目标")
    priority: int = Field(default=1, ge=1, le=5, description="优先级 1-5")


class CharacterProfile(BaseModel):
    """Full character profile used by the character agent."""

    character_id: str = Field(description="唯一标识符")
    name: str = Field(description="角色名称")
    age: int = Field(default=30, description="年龄")
    gender: str = Field(default="", description="性别")
    role: str = Field(default="", description="故事角色 (主角/反派/配角等)")
    backstory: str = Field(default="", description="背景故事")
    personality: PersonalityTraits = Field(default_factory=PersonalityTraits)
    goals: list[Goal] = Field(default_factory=list, description="目标列表")
    speaking_style: str = Field(default="", description="说话风格描述")
    appearance: str = Field(default="", description="外貌描述")
    quirks: list[str] = Field(default_factory=list, description="性格特点/小癖好")
    core_values: list[str] = Field(default_factory=list, description="核心价值观")
