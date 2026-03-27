"""World-building models — power systems, locations, factions, history."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PowerSystem(BaseModel):
    """A power / magic / martial arts system in the fictional world."""

    name: str = Field(description="力量体系名称")
    description: str = Field(description="体系描述")
    levels: list[str] = Field(default_factory=list, description="等级划分 (从低到高)")
    rules: list[str] = Field(default_factory=list, description="核心规则与限制")


class Location(BaseModel):
    """A notable place in the fictional world."""

    name: str = Field(description="地点名称")
    description: str = Field(description="地点描述")
    significance: str = Field(default="", description="剧情意义")
    connected_locations: list[str] = Field(default_factory=list, description="连通地点")
    controlling_faction: str = Field(default="", description="控制势力")


class Faction(BaseModel):
    """An organization or group in the fictional world."""

    name: str = Field(description="势力名称")
    description: str = Field(description="势力描述")
    ideology: str = Field(default="", description="核心理念")
    leader: str = Field(default="", description="领袖")
    allies: list[str] = Field(default_factory=list, description="盟友势力")
    enemies: list[str] = Field(default_factory=list, description="敌对势力")


class HistoryEvent(BaseModel):
    """A significant historical event in the fictional world."""

    name: str = Field(description="事件名称")
    description: str = Field(description="事件描述")
    era: str = Field(default="", description="所属时代")
    impact: str = Field(default="", description="对当前世界的影响")


class WorldView(BaseModel):
    """Complete world-building data — the living backdrop of the story."""

    world_name: str = Field(description="世界名称")
    world_description: str = Field(description="世界总体描述")
    era: str = Field(default="", description="故事所处时代")
    power_systems: list[PowerSystem] = Field(default_factory=list, description="力量体系")
    locations: list[Location] = Field(default_factory=list, description="重要地点")
    factions: list[Faction] = Field(default_factory=list, description="势力组织")
    history: list[HistoryEvent] = Field(default_factory=list, description="历史大事记")
    cultural_notes: list[str] = Field(default_factory=list, description="文化风俗")
    taboos_and_rules: list[str] = Field(default_factory=list, description="禁忌与世界规则")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_location(self, name: str) -> Location | None:
        """Find a location by name (case-insensitive partial match)."""
        for loc in self.locations:
            if name in loc.name or loc.name in name:
                return loc
        return None

    def get_faction(self, name: str) -> Faction | None:
        """Find a faction by name (case-insensitive partial match)."""
        for fac in self.factions:
            if name in fac.name or fac.name in name:
                return fac
        return None

    def summary(self) -> str:
        """Compress the world-view into a concise LLM context string."""
        parts: list[str] = [
            f"## 世界观: {self.world_name}",
            self.world_description,
            f"时代: {self.era}" if self.era else "",
        ]

        if self.power_systems:
            parts.append("\n### 力量体系")
            for ps in self.power_systems:
                levels = " → ".join(ps.levels) if ps.levels else ""
                parts.append(f"- **{ps.name}**: {ps.description}")
                if levels:
                    parts.append(f"  等级: {levels}")

        if self.factions:
            parts.append("\n### 势力")
            for f in self.factions:
                parts.append(f"- **{f.name}**: {f.description} (领袖: {f.leader})")

        if self.locations:
            parts.append("\n### 重要地点")
            for loc in self.locations:
                parts.append(f"- **{loc.name}**: {loc.description}")

        if self.cultural_notes:
            parts.append("\n### 文化风俗")
            for note in self.cultural_notes:
                parts.append(f"- {note}")

        if self.taboos_and_rules:
            parts.append("\n### 禁忌与规则")
            for rule in self.taboos_and_rules:
                parts.append(f"- {rule}")

        return "\n".join(p for p in parts if p)
