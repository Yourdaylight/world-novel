"""Character skill models — user-manageable ability/behavior/growth definitions.

A skill is the third control lever for character evolution (besides soul.md values
and episodic memory): it defines what the character is good at, how it tends to
behave, and which direction its growth should converge toward.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Skill categories
SKILL_CATEGORY_ABILITY = "ability"   # 专长：角色擅长什么（战斗/医术/权谋/口才）
SKILL_CATEGORY_HABIT = "habit"       # 行为模式：谨慎/冲动/慷慨/记仇
SKILL_CATEGORY_GROWTH = "growth"     # 演化方向：正在成为什么样的人


class CharacterSkill(BaseModel):
    """A single user-managed skill for a character agent."""

    character_id: str = Field(description="所属角色 ID")
    skill_id: str = Field(default="", description="slug 唯一标识，如 swordsmanship")
    name: str = Field(description="显示名，如 剑术")
    category: str = Field(
        default=SKILL_CATEGORY_ABILITY,
        description="ability(专长) / habit(行为模式) / growth(演化方向)",
    )
    description: str = Field(default="", description="行为描述：角色如何使用这项技能")
    trigger_conditions: str = Field(default="", description="触发条件：什么情境下会动用")
    level: float = Field(default=0.3, ge=0.0, le=1.0, description="熟练度 0-1")
    direction: str = Field(default="", description="演化指向：该技能如何塑造成长")
    enabled: bool = Field(default=True, description="是否启用")
    priority: int = Field(default=0, ge=0, description="注入顺序/权重，越大越靠前")
    created_at: str = Field(default="", description="创建时间")
