"""Timeline models — story eras and events for temporal organization."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StoryEra(BaseModel):
    """故事世界中的一个时代/纪元"""

    era_id: str = Field(description="时代ID, 如 'era_youth'")
    name: str = Field(description="时代名称, 如 '少年时期'")
    description: str = Field(default="", description="时代描述")
    order: int = Field(description="排序: 0, 1, 2...")
    story_time_start: str = Field(default="", description="世界内时间标签起始, 如 '太和元年春'")
    story_time_end: str = Field(default="", description="世界内时间标签结束")
    chapter_start: int = Field(description="对应章节范围起始 (inclusive)")
    chapter_end: int = Field(description="对应章节范围结束 (inclusive)")
    volume_index: int = Field(default=0, description="所属卷序号")


class TimelineEvent(BaseModel):
    """时间线上的一个事件"""

    event_id: str = Field(description="事件ID")
    era_id: str = Field(description="所属时代ID")
    chapter_index: int = Field(description="发生章节")
    story_time: str = Field(default="", description="故事内时间标记")
    event_type: str = Field(
        description="事件类型: world_event | character_event | god_intervention | time_skip",
    )
    title: str = Field(description="事件标题")
    description: str = Field(default="", description="事件描述")
    affected_characters: list[str] = Field(default_factory=list, description="受影响角色ID列表")
    affected_locations: list[str] = Field(default_factory=list, description="受影响地点列表")
    source: str = Field(default="director", description="来源: director | god_agent | character_action")
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="重要度 0-1")


class StoryTimeline(BaseModel):
    """主时间线 — 命运Agent所有，全局可读"""

    eras: list[StoryEra] = Field(default_factory=list)
    events: list[TimelineEvent] = Field(default_factory=list)

    def get_current_era(self, chapter_index: int) -> StoryEra | None:
        """根据章节号获取当前时代"""
        for era in self.eras:
            if era.chapter_start <= chapter_index <= era.chapter_end:
                return era
        # Fallback: return last era if chapter exceeds all ranges
        if self.eras:
            return self.eras[-1]
        return None

    def get_events_in_era(self, era_id: str) -> list[TimelineEvent]:
        """获取某个时代的所有事件"""
        return [e for e in self.events if e.era_id == era_id]

    def get_events_for_chapter(self, chapter_index: int) -> list[TimelineEvent]:
        """获取某个章节的所有事件"""
        return [e for e in self.events if e.chapter_index == chapter_index]

    def get_events_for_character(self, character_id: str) -> list[TimelineEvent]:
        """获取影响某个角色的所有事件"""
        return [e for e in self.events if character_id in e.affected_characters]

    def summary(self) -> str:
        """生成时间线摘要，用于LLM上下文"""
        parts: list[str] = []
        for era in sorted(self.eras, key=lambda e: e.order):
            era_events = self.get_events_in_era(era.era_id)
            parts.append(f"【{era.name}】({era.story_time_start} — {era.story_time_end})")
            for ev in sorted(era_events, key=lambda e: e.chapter_index):
                marker = "⭐" if ev.importance >= 0.7 else "·"
                parts.append(f"  {marker} [第{ev.chapter_index + 1}章] {ev.title}")
        return "\n".join(parts)
