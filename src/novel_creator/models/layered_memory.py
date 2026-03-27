"""Models for the layered memory system — beliefs, schemas, trauma."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field


class CoreBelief(BaseModel):
    belief_id: str = ""
    character_id: str
    content: str = Field(description="核心信念内容，如'权力终将腐蚀一切'")
    strength: float = Field(default=0.5, ge=0.0, le=1.0, description="信念强度 0-1")
    origin_chapter: int = 0
    last_reinforced_chapter: int = 0


class RelationshipSchema(BaseModel):
    schema_id: str = ""
    character_id: str
    target_id: str
    mental_model: str = Field(description="对目标角色的心智模型，如'苏瑶看似柔弱实则坚强'")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    last_updated_chapter: int = 0


class TraumaMemory(BaseModel):
    trauma_id: str = ""
    character_id: str
    content: str = Field(description="创伤/锚点记忆内容")
    trauma_type: str = Field(default="anchor", description="anchor(正面锚点)/trauma(创伤)")
    trigger_keywords: list[str] = Field(default_factory=list, description="触发关键词")
    emotional_impact: dict[str, float] = Field(default_factory=dict, description="情感影响")
    origin_chapter: int = 0
    importance: float = 0.8


class ReflectionLog(BaseModel):
    reflection_id: str = ""
    character_id: str
    chapter_index: int
    beliefs_updated: int = 0
    schemas_updated: int = 0
    traumas_identified: int = 0
    summary: str = ""
