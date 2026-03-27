"""Narrative output models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Scene(BaseModel):
    """A rendered scene within a chapter."""

    scene_index: int
    content: str = Field(description="场景叙事文本")
    pov_character: str = Field(default="", description="视角角色")


class Chapter(BaseModel):
    """A complete rendered chapter."""

    chapter_index: int
    title: str
    scenes: list[Scene] = Field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(s.content for s in self.scenes)


class NovelOutput(BaseModel):
    """The complete novel output."""

    title: str
    genre: str
    chapters: list[Chapter] = Field(default_factory=list)

    @property
    def full_text(self) -> str:
        parts: list[str] = [f"# {self.title}\n"]
        for ch in self.chapters:
            parts.append(f"\n## 第{ch.chapter_index + 1}章 {ch.title}\n")
            parts.append(ch.full_text)
        return "\n".join(parts)

    @property
    def word_count(self) -> int:
        return len(self.full_text)
