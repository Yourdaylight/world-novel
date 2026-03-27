"""Foreshadowing and plot-thread tracking models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ForeshadowStatus(str, Enum):
    """Lifecycle of a foreshadowing element."""

    PLANTED = "planted"
    REINFORCED = "reinforced"
    PAYOFF = "payoff"
    DANGLING = "dangling"


class Foreshadow(BaseModel):
    """A single foreshadowing element tracked across the novel."""

    foreshadow_id: str = Field(description="伏笔唯一ID")
    description: str = Field(description="伏笔内容描述")
    hint_text: str = Field(default="", description="暗示文本 (写手可用的参考)")
    planted_chapter: int = Field(description="埋设章节 (0-based)")
    expected_payoff_chapter: int = Field(description="预期回收章节 (0-based)")
    actual_payoff_chapter: int | None = Field(default=None, description="实际回收章节")
    status: ForeshadowStatus = Field(default=ForeshadowStatus.PLANTED, description="当前状态")
    importance: str = Field(default="minor", description="重要性: major / minor / twist")
    related_characters: list[str] = Field(default_factory=list, description="关联角色ID")
    related_plot_thread: str = Field(default="", description="所属剧情线ID")


class PlotThread(BaseModel):
    """A storyline thread that spans multiple chapters."""

    thread_id: str = Field(description="剧情线唯一ID")
    name: str = Field(description="剧情线名称")
    description: str = Field(default="", description="剧情线描述")
    status: str = Field(default="active", description="active / resolved / suspended")
    start_chapter: int = Field(default=0, description="起始章节 (0-based)")
    key_characters: list[str] = Field(default_factory=list, description="关键角色ID")
    foreshadow_ids: list[str] = Field(default_factory=list, description="关联伏笔ID列表")
    chapter_progress: dict[int, str] = Field(
        default_factory=dict,
        description="每章推进摘要 {chapter_index: summary}",
    )
