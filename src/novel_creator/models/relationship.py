"""Relationship models between characters."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Relationship(BaseModel):
    """Directed relationship from one character to another."""

    source_id: str = Field(description="关系发起角色ID")
    target_id: str = Field(description="关系目标角色ID")
    relationship_type: str = Field(default="陌生人", description="关系类型 (朋友/敌人/恋人/师徒等)")
    trust: float = Field(default=0.0, ge=-1.0, le=1.0, description="信任度 -1~1")
    affection: float = Field(default=0.0, ge=-1.0, le=1.0, description="好感度 -1~1")
    description: str = Field(default="", description="关系描述")


class RelationshipGraph(BaseModel):
    """Graph of all character relationships."""

    relationships: list[Relationship] = Field(default_factory=list)

    def get_relationship(self, source_id: str, target_id: str) -> Relationship | None:
        for r in self.relationships:
            if r.source_id == source_id and r.target_id == target_id:
                return r
        return None

    def get_relationships_for(self, character_id: str) -> list[Relationship]:
        return [r for r in self.relationships if r.source_id == character_id or r.target_id == character_id]

    def upsert(self, rel: Relationship) -> None:
        for i, r in enumerate(self.relationships):
            if r.source_id == rel.source_id and r.target_id == rel.target_id:
                self.relationships[i] = rel
                return
        self.relationships.append(rel)
