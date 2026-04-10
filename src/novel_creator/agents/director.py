"""Director Agent — generates story outline, character profiles, and relationship graph."""

from __future__ import annotations

from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from novel_creator.llm import get_llm, invoke_with_retry
from novel_creator.models.character import CharacterProfile
from novel_creator.models.relationship import RelationshipGraph
from novel_creator.models.story import StoryOutline


class DirectorOutput(BaseModel):
    """Combined output from the Director agent."""
    outline: StoryOutline = Field(description="完整故事大纲")
    characters: list[CharacterProfile] = Field(description="角色档案列表")
    relationships: RelationshipGraph = Field(description="角色关系图谱")


SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "director.md").read_text()


def create_director_chain(*, num_volumes: int = 0):
    """Create the director LLM chain with structured output.

    Parameters
    ----------
    num_volumes : int
        If > 0, the director will be asked to organise chapters into volumes.
    """
    llm = get_llm("director")
    structured_llm = llm.with_structured_output(DirectorOutput)

    volume_instruction = ""
    if num_volumes > 0:
        volume_instruction = (
            f"\n**卷数**: {num_volumes}\n"
            "请将章节组织为多个卷 (Volume)，每卷有独立的标题、主题和剧情弧线目标。"
            "在 outline.volumes 中输出卷结构，每卷指定 chapter_start 和 chapter_end。"
            "在每个 ChapterOutline 中设置对应的 volume_index。"
        )

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", (
            "请为我设计一部小说:\n\n"
            "**类型**: {genre}\n"
            "**主题**: {theme}\n"
            "**前提**: {premise}\n"
            "**章节数**: {num_chapters}\n"
            "**主要角色数**: {num_characters}\n"
            f"{volume_instruction}\n\n"
            "请输出完整的故事大纲、角色档案和关系图谱。"
            "确保每个章节有2-3个场景节拍，每个场景明确指定涉及的角色ID。"
            "角色ID使用英文小写 (如 hero, villain, mentor)。"
        )),
    ])
    return prompt | structured_llm


async def run_director(
    genre: str,
    theme: str,
    premise: str,
    num_chapters: int = 3,
    num_characters: int = 3,
    *,
    num_volumes: int = 0,
    total_chapters: int = 0,
) -> DirectorOutput:
    """Run the director agent and return the complete planning output."""
    chain = create_director_chain(num_volumes=num_volumes)
    result = await invoke_with_retry(
        chain,
        {
            "genre": genre,
            "theme": theme,
            "premise": premise,
            "num_chapters": num_chapters,
            "num_characters": num_characters,
        },
        description="Director planning",
        role="director",
        chapter_index=-1,
    )
    return result
