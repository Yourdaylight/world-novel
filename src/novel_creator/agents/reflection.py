"""Reflection Agent — character self-examination between chapters.

After every 2-3 chapters, each character reviews their recent experiences
and updates their deep memory layers: core beliefs, relationship schemas,
and trauma/anchor memories.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from novel_creator.llm import get_llm, invoke_with_retry
from novel_creator.log import get_logger
from novel_creator.memory.character_memory import CharacterMemory
from novel_creator.models.layered_memory import (
    CoreBelief,
    ReflectionLog,
    RelationshipSchema,
    TraumaMemory,
)

logger = get_logger("novel_creator.agents.reflection")

REFLECTION_PROMPT = (Path(__file__).parent.parent / "prompts" / "reflection.md").read_text()


# ======================================================================
# Structured output models
# ======================================================================


class BeliefUpdate(BaseModel):
    content: str = Field(description="信念内容")
    strength: float = Field(default=0.5, ge=0.0, le=1.0, description="信念强度")
    is_new: bool = Field(default=True, description="是新信念还是对已有信念的强化")
    existing_belief_id: str = Field(default="", description="如果是强化已有信念，填写belief_id")


class SchemaUpdate(BaseModel):
    target_id: str = Field(description="目标角色ID")
    mental_model: str = Field(description="对该角色的心智模型描述")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class TraumaIdentification(BaseModel):
    content: str = Field(description="刻骨铭心的记忆内容")
    trauma_type: str = Field(default="anchor", description="anchor(正面)/trauma(创伤)")
    trigger_keywords: list[str] = Field(default_factory=list, description="触发关键词")
    emotional_impact: dict[str, float] = Field(default_factory=dict, description="情感影响")


class ReflectionOutput(BaseModel):
    summary: str = Field(description="反思总结（一段话）")
    belief_updates: list[BeliefUpdate] = Field(default_factory=list, description="信念变化")
    schema_updates: list[SchemaUpdate] = Field(default_factory=list, description="对他人认知变化")
    trauma_identifications: list[TraumaIdentification] = Field(default_factory=list, description="新识别的创伤/锚点记忆")


# ======================================================================
# Reflection Agent
# ======================================================================


class ReflectionAgent:
    """Character self-examination agent.

    Runs between chapters to let each character reflect on recent experiences
    and evolve their internal state (beliefs, schemas, trauma/anchors).
    """

    def __init__(self):
        self.llm = get_llm("director")

    async def reflect(
        self,
        character_id: str,
        memory: CharacterMemory,
        chapter_index: int,
    ) -> ReflectionOutput:
        """Run a reflection cycle for a character.

        Parameters
        ----------
        character_id : str
            The character performing the reflection.
        memory : CharacterMemory
            The character's unified memory facade.
        chapter_index : int
            The current chapter index (0-based, already incremented past the
            chapter that was just completed).
        """
        # --- Gather context ---
        context = await self._build_context(memory, chapter_index)

        # --- Call LLM with structured output ---
        prompt = ChatPromptTemplate.from_messages([
            ("system", REFLECTION_PROMPT),
            ("human", "请以这个角色的内心视角进行深层反思，输出结构化的反思结果。"),
        ])
        structured_llm = self.llm.with_structured_output(ReflectionOutput)
        chain = prompt | structured_llm

        output: ReflectionOutput = await invoke_with_retry(
            chain,
            context,
            description=f"Reflection for {character_id} (ch{chapter_index})",
            role="reflection", chapter_index=chapter_index,
        )

        # --- Apply updates ---
        await self._apply_updates(character_id, memory, chapter_index, output)

        return output

    async def _build_context(
        self,
        memory: CharacterMemory,
        chapter_index: int,
    ) -> dict[str, str]:
        """Build the context dict for the reflection prompt variables."""
        # Character identity
        profile = await memory.get_profile()
        if profile:
            character_context = (
                f"{profile.name} ({profile.role})\n"
                f"背景: {profile.backstory}\n"
                f"说话风格: {profile.speaking_style}\n"
                f"目标: {'; '.join(g.description for g in profile.goals)}"
            )
        else:
            character_context = f"角色ID: {memory.character_id}"

        # Recent episodic memories (last 2-3 chapters)
        recent_memories_parts: list[str] = []
        start_chapter = max(0, chapter_index - 3)
        for ch_idx in range(start_chapter, chapter_index):
            ch_memories = await memory.episodic.get_by_chapter(ch_idx)
            if ch_memories:
                recent_memories_parts.append(f"--- 第{ch_idx + 1}章 ---")
                for m in ch_memories:
                    recent_memories_parts.append(f"  {m.content}")
        recent_memories = "\n".join(recent_memories_parts) if recent_memories_parts else "（暂无近期记忆）"

        # Emotional state
        emotion = await memory.emotional.get_latest()
        emotional_state = emotion.summary()

        # Relationships
        rels = await memory.relationships.get_all()
        if rels:
            rel_parts = []
            for r in rels:
                other = r.target_id if r.source_id == memory.character_id else r.source_id
                rel_parts.append(f"- {other}: {r.relationship_type} (信任:{r.trust:+.1f} 好感:{r.affection:+.1f})")
            relationships = "\n".join(rel_parts)
        else:
            relationships = "（暂无人际关系记录）"

        # Current beliefs
        beliefs = await memory.beliefs.get_all()
        if beliefs:
            belief_parts = []
            for b in beliefs:
                strength_label = "坚定" if b.strength > 0.7 else "动摇" if b.strength < 0.3 else "一般"
                belief_parts.append(f"- [{strength_label}] (id={b.belief_id}) {b.content}")
            current_beliefs = "\n".join(belief_parts)
        else:
            current_beliefs = "（暂无核心信念）"

        # Current schemas
        schemas = await memory.schemas.get_all()
        if schemas:
            schema_parts = []
            for s in schemas:
                schema_parts.append(f"- 对{s.target_id}: {s.mental_model} (信心:{s.confidence:.1f})")
            current_schemas = "\n".join(schema_parts)
        else:
            current_schemas = "（暂无对他人的认知记录）"

        # Current traumas/anchors
        traumas = await memory.traumas.get_all()
        if traumas:
            trauma_parts = []
            for t in traumas:
                type_label = "创伤" if t.trauma_type == "trauma" else "锚点"
                trauma_parts.append(f"- [{type_label}] {t.content}")
            current_traumas = "\n".join(trauma_parts)
        else:
            current_traumas = "（暂无刻骨铭心的记忆）"

        return {
            "character_context": character_context,
            "recent_memories": recent_memories,
            "emotional_state": emotional_state,
            "relationships": relationships,
            "current_beliefs": current_beliefs,
            "current_schemas": current_schemas,
            "current_traumas": current_traumas,
        }

    async def _apply_updates(
        self,
        character_id: str,
        memory: CharacterMemory,
        chapter_index: int,
        output: ReflectionOutput,
    ) -> None:
        """Apply the reflection output to the character's deep memory layers."""
        beliefs_updated = 0
        schemas_updated = 0
        traumas_identified = 0

        # --- Belief updates ---
        for bu in output.belief_updates:
            if bu.is_new:
                await memory.beliefs.add(CoreBelief(
                    character_id=character_id,
                    content=bu.content,
                    strength=bu.strength,
                    origin_chapter=chapter_index,
                    last_reinforced_chapter=chapter_index,
                ))
            else:
                if bu.existing_belief_id:
                    await memory.beliefs.update_strength(
                        bu.existing_belief_id, bu.strength, chapter_index,
                    )
            beliefs_updated += 1

        # --- Schema updates ---
        for su in output.schema_updates:
            await memory.schemas.upsert(RelationshipSchema(
                character_id=character_id,
                target_id=su.target_id,
                mental_model=su.mental_model,
                confidence=su.confidence,
                last_updated_chapter=chapter_index,
            ))
            schemas_updated += 1

        # --- Trauma identifications ---
        for ti in output.trauma_identifications:
            await memory.traumas.add(TraumaMemory(
                character_id=character_id,
                content=ti.content,
                trauma_type=ti.trauma_type,
                trigger_keywords=ti.trigger_keywords,
                emotional_impact=ti.emotional_impact,
                origin_chapter=chapter_index,
            ))
            traumas_identified += 1

        # --- Log the reflection ---
        await memory.reflections.log_reflection(ReflectionLog(
            character_id=character_id,
            chapter_index=chapter_index,
            beliefs_updated=beliefs_updated,
            schemas_updated=schemas_updated,
            traumas_identified=traumas_identified,
            summary=output.summary,
        ))
