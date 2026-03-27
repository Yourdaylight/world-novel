"""Reviewer Agent — checks foreshadowing quality in generated chapters."""

from __future__ import annotations

from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from novel_creator.llm import get_llm, invoke_with_retry
from novel_creator.models.foreshadow import Foreshadow


SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "reviewer.md").read_text()


class ForeshadowCheckItem(BaseModel):
    """Review result for a single foreshadow."""

    foreshadow_id: str = Field(description="伏笔ID")
    found: bool = Field(description="是否在文本中找到")
    quality_score: int = Field(default=0, description="质量评分 0-5")
    evidence: str = Field(default="", description="文本中的相关片段")
    suggestion: str = Field(default="", description="改进建议")


class ForeshadowCheckResult(BaseModel):
    """Complete review output for one chapter."""

    checks: list[ForeshadowCheckItem] = Field(default_factory=list, description="逐条伏笔检查结果")
    dangling_warnings: list[str] = Field(default_factory=list, description="悬空伏笔警告")
    overall_score: int = Field(default=5, description="总体评分 0-10")


class ReviewerAgent:
    """Reviews a chapter for foreshadowing compliance."""

    def __init__(self) -> None:
        self.llm = get_llm("reviewer")

    async def check_chapter(
        self,
        chapter_text: str,
        expected_plants: list[Foreshadow],
        expected_payoffs: list[Foreshadow],
        dangling: list[Foreshadow] | None = None,
    ) -> ForeshadowCheckResult:
        """Check how well foreshadows were handled in *chapter_text*."""
        plants_text = "\n".join(
            f"- [{f.foreshadow_id}] {f.description} (暗示: {f.hint_text})"
            for f in expected_plants
        ) or "无"
        payoffs_text = "\n".join(
            f"- [{f.foreshadow_id}] {f.description} (原始暗示: {f.hint_text}, 埋设于第{f.planted_chapter+1}章)"
            for f in expected_payoffs
        ) or "无"
        dangling_text = "\n".join(
            f"- [{f.foreshadow_id}] {f.description} (预期第{f.expected_payoff_chapter+1}章回收)"
            for f in (dangling or [])
        ) or "无"

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", (
                "## 本章文本\n\n{chapter_text}\n\n"
                "## 应埋设的伏笔\n{plants_text}\n\n"
                "## 应回收的伏笔\n{payoffs_text}\n\n"
                "## 悬空伏笔 (超期未回收)\n{dangling_text}\n\n"
                "请按要求检查并输出结构化结果。"
            )),
        ])
        structured_llm = self.llm.with_structured_output(ForeshadowCheckResult)
        chain = prompt | structured_llm
        result: ForeshadowCheckResult = await invoke_with_retry(
            chain,
            {
                "chapter_text": chapter_text[:6000],
                "plants_text": plants_text,
                "payoffs_text": payoffs_text,
                "dangling_text": dangling_text,
            },
            description="Foreshadow review",
            role="reviewer",
        )
        return result
