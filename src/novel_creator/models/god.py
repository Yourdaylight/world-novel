"""God Agent (命运Agent) decision models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from novel_creator.models.timeline import StoryEra


class TimeProgression(BaseModel):
    """时间推进决策"""

    time_skip: str = Field(default="", description="时间跳跃描述, 如 '三年后'")
    new_era: StoryEra | None = Field(default=None, description="若需进入新时代")
    description: str = Field(default="", description="时间推进叙述")


class WorldEvent(BaseModel):
    """世界事件"""

    event_type: str = Field(description="事件类型: natural_disaster | political_change | discovery | war | cultural_shift")
    title: str = Field(description="事件标题")
    description: str = Field(description="事件描述")
    affected_characters: list[str] = Field(default_factory=list, description="受影响角色ID列表")
    affected_locations: list[str] = Field(default_factory=list, description="受影响地点列表")
    importance: float = Field(default=0.7, ge=0.0, le=1.0, description="重要度")
    story_time: str = Field(default="", description="故事内时间标记")


class SubplotTrigger(BaseModel):
    """支线触发"""

    trigger_type: str = Field(description="触发类型: chance_encounter | revelation | betrayal | crisis | quest")
    description: str = Field(description="支线描述")
    involved_characters: list[str] = Field(default_factory=list, description="涉及角色ID列表")
    setup: str = Field(default="", description="下章如何体现这个支线")


class WorldStateChange(BaseModel):
    """世界状态变化"""

    target: str = Field(description="变化目标: faction:xxx | location:xxx | power_system:xxx")
    change_description: str = Field(description="变化描述")


class GodDecision(BaseModel):
    """命运Agent章间决策输出"""

    decision_id: str = Field(description="决策ID")
    chapter_index: int = Field(description="对应章节索引 (刚完成的章节)")
    time_progression: TimeProgression | None = Field(default=None, description="时间推进决策")
    world_events: list[WorldEvent] = Field(default_factory=list, description="世界事件列表")
    subplot_triggers: list[SubplotTrigger] = Field(default_factory=list, description="支线触发列表")
    world_state_changes: list[WorldStateChange] = Field(default_factory=list, description="世界状态变化列表")
    next_chapter_guidance: str = Field(default="", description="对下章角色/写手的指导")

    def summary(self) -> str:
        """生成决策摘要"""
        parts: list[str] = []
        if self.time_progression and self.time_progression.time_skip:
            parts.append(f"⏳ 时间跳跃: {self.time_progression.time_skip}")
            if self.time_progression.new_era:
                parts.append(f"  → 进入新时代: {self.time_progression.new_era.name}")
        for we in self.world_events:
            parts.append(f"🌍 {we.title}: {we.description[:80]}")
        for st in self.subplot_triggers:
            parts.append(f"🔀 {st.trigger_type}: {st.description[:80]}")
        if self.next_chapter_guidance:
            parts.append(f"📌 叙事指导: {self.next_chapter_guidance[:120]}")
        return "\n".join(parts) if parts else "无重大干预"
