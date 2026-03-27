"""Generation checkpoint model for pause / resume support."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GenerationCheckpoint(BaseModel):
    """Snapshot of generation state — allows pause and resume."""

    checkpoint_id: str = Field(description="检查点唯一ID")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    last_completed_chapter: int = Field(description="最后完成的章节 (0-based)")
    phase: str = Field(default="simulating", description="当前阶段")
    state_json: str = Field(default="", description="完整 state 序列化 JSON")
    novel_title: str = Field(default="", description="小说标题")
    total_chapters: int = Field(default=0, description="总章节数")
    completed_chapters: int = Field(default=0, description="已完成章节数")
