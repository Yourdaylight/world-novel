"""Story outline and structure models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SceneBeat(BaseModel):
    """A single beat within a scene — the atomic unit of story planning."""

    scene_index: int = Field(description="场景在章节中的序号 (0-based)")
    location: str = Field(description="场景发生地点")
    involved_characters: list[str] = Field(description="参与角色ID列表")
    objective: str = Field(description="本场景要推进的剧情目标")
    conflict: str = Field(default="", description="场景中的冲突或张力")
    tone: str = Field(default="neutral", description="场景情绪基调")
    # V2: foreshadowing instructions
    foreshadows_to_plant: list[str] = Field(
        default_factory=list, description="本场景需要埋设的伏笔ID列表",
    )
    foreshadows_to_payoff: list[str] = Field(
        default_factory=list, description="本场景需要回收的伏笔ID列表",
    )


class ChapterOutline(BaseModel):
    """Outline for a single chapter."""

    chapter_index: int = Field(description="章节序号 (0-based)")
    title: str = Field(description="章节标题")
    summary: str = Field(description="章节概要")
    scenes: list[SceneBeat] = Field(default_factory=list, description="场景节拍列表 (保留做向后兼容)")
    key_events: list[str] = Field(default_factory=list, description="关键事件")
    # V2: volume association
    volume_index: int = Field(default=0, description="所属卷序号 (0-based)")
    # V3: timeline association
    story_time: str = Field(default="", description="本章在故事世界中的时间标记")
    era_id: str = Field(default="", description="所属时代ID")
    # V9: beat-based simulation — chapter maps to a range of SimulationBeats
    beat_range_start: int | None = Field(default=None, description="起始 beat sequence (inclusive)")
    beat_range_end: int | None = Field(default=None, description="结束 beat sequence (inclusive)")


class Volume(BaseModel):
    """A volume (卷) grouping several chapters together."""

    volume_index: int = Field(description="卷序号 (0-based)")
    title: str = Field(description="卷标题")
    summary: str = Field(default="", description="卷概要")
    theme: str = Field(default="", description="本卷主题")
    chapter_start: int = Field(description="起始章节序号 (0-based, inclusive)")
    chapter_end: int = Field(description="结束章节序号 (0-based, inclusive)")
    arc_goal: str = Field(default="", description="本卷剧情弧线目标")


class StoryOutline(BaseModel):
    """Complete story outline produced by the Director agent."""

    title: str = Field(description="小说标题")
    genre: str = Field(description="小说类型")
    theme: str = Field(description="核心主题")
    premise: str = Field(description="故事前提")
    setting: str = Field(description="故事背景设定")
    chapters: list[ChapterOutline] = Field(default_factory=list, description="章节大纲列表")
    central_conflict: str = Field(default="", description="核心冲突")
    resolution_direction: str = Field(default="", description="结局走向")
    # V2: volumes
    volumes: list[Volume] = Field(default_factory=list, description="卷结构列表")
