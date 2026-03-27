"""Character Agent — independent consciousness simulation for each character."""

from __future__ import annotations

from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from novel_creator.llm import get_llm, invoke_with_retry
from novel_creator.memory.character_memory import CharacterMemory
from novel_creator.models.memory import ActionType, CharacterAction, EmotionalState, EpisodicMemory

PROMPT_TEMPLATE = (Path(__file__).parent.parent / "prompts" / "character.md").read_text()


class CharacterActionOutput(BaseModel):
    """Structured output from a character's scene processing."""
    actions: list[ActionItem] = Field(description="角色在本场景中的行动列表")
    emotional_changes: dict[str, float] = Field(
        default_factory=dict,
        description="情感维度变化量 (如 {'happiness': 0.1, 'anger': -0.2})",
    )
    memory_summary: str = Field(default="", description="角色对本场景的记忆总结")
    relationship_changes: list[RelationshipChange] = Field(
        default_factory=list, description="对其他角色关系的变化",
    )


class ActionItem(BaseModel):
    action_type: str = Field(description="dialogue/behavior/thought/reaction")
    content: str = Field(description="具体内容")
    target: str | None = Field(default=None, description="目标角色ID")


class RelationshipChange(BaseModel):
    target_id: str
    trust_delta: float = 0.0
    affection_delta: float = 0.0
    new_description: str = ""


# Redefine to fix forward reference
CharacterActionOutput.model_rebuild()


class CharacterAgent:
    """An independent agent instance for a single character."""

    def __init__(
        self,
        character_id: str,
        memory: CharacterMemory,
        *,
        agent_dir: Path | None = None,
    ):
        self.character_id = character_id
        self.memory = memory
        self.agent_dir = agent_dir
        self.llm = get_llm("character")

    async def process_scene(
        self,
        chapter_index: int,
        scene_index: int,
        location: str,
        scene_objective: str,
        present_character_ids: list[str],
        other_actions: list[CharacterAction] | None = None,
        *,
        world_context: str = "",
        location_detail: str = "",
        timeline=None,
    ) -> list[CharacterAction]:
        """Process a scene: recall memories, decide actions, update state.

        Parameters
        ----------
        world_context : str, optional
            World-view summary injected into the system prompt so the
            character is aware of the world rules.
        location_detail : str, optional
            Detailed description of the current location.
        timeline : StoryTimeline, optional
            Timeline for era-aware memory recall.
        """
        # 1. Build context from memory (timeline-aware if available)
        memory_context = await self.memory.get_context_window(
            chapter_index, scene_index, timeline=timeline,
        )
        profile = await self.memory.get_profile()
        name = profile.name if profile else self.character_id

        # 2. Build other characters' actions context
        others_context = ""
        if other_actions:
            parts = []
            for a in other_actions:
                prefix = {"dialogue": "说", "behavior": "做", "thought": "", "reaction": "反应"}.get(a.action_type.value, "")
                if a.action_type == ActionType.THOUGHT:
                    continue  # Characters can't see others' thoughts
                parts.append(f"  {a.character_id} {prefix}: {a.content}")
            if parts:
                others_context = "\n## 其他角色的行为\n" + "\n".join(parts)

        # 2b. Build world/location context block
        world_block = ""
        if world_context:
            world_block += f"\n## 世界观背景\n{world_context}\n"
        if location_detail:
            world_block += f"\n## 当前地点详情\n{location_detail}\n"

        # V3: Inject soul.md if available
        soul_block = ""
        if self.agent_dir:
            soul_path = self.agent_dir / "soul.md"
            if soul_path.exists():
                try:
                    soul_text = soul_path.read_text(encoding="utf-8")
                    soul_block = f"\n## 灵魂深处\n{soul_text}\n"
                except Exception:
                    pass

        # 3. Call LLM
        prompt = ChatPromptTemplate.from_messages([
            ("system", PROMPT_TEMPLATE.format(
                name=name,
                identity_context=memory_context,
                location=location,
                scene_objective=scene_objective,
                present_characters=", ".join(present_character_ids),
                memory_context=memory_context,
            ) + world_block + soul_block),
            ("human", (
                f"当前是第{chapter_index + 1}章第{scene_index + 1}个场景。\n"
                f"地点: {location}\n"
                f"场景目标: {scene_objective}\n"
                f"在场角色: {', '.join(present_character_ids)}\n"
                f"{others_context}\n\n"
                "请以角色的身份做出反应，输出你的行动列表和情感变化。"
            )),
        ])
        structured_llm = self.llm.with_structured_output(CharacterActionOutput)
        chain = prompt | structured_llm
        output: CharacterActionOutput = await invoke_with_retry(
            chain, {}, description=f"Character {self.character_id} scene action",
            role="character", chapter_index=chapter_index,
        )

        # 4. Convert to CharacterAction models and persist
        actions: list[CharacterAction] = []
        for item in output.actions:
            try:
                action_type = ActionType(item.action_type)
            except ValueError:
                action_type = ActionType.BEHAVIOR
            action = CharacterAction(
                character_id=self.character_id,
                chapter_index=chapter_index,
                scene_index=scene_index,
                action_type=action_type,
                content=item.content,
                target_character_id=item.target,
                emotional_shift=output.emotional_changes,
            )
            actions.append(action)
            await self.memory.record_action(action)

        # 5. Update emotional state
        current_emotion = await self.memory.emotional.get_latest()
        new_emotion = current_emotion.apply_shift(output.emotional_changes)
        new_emotion.chapter_index = chapter_index
        new_emotion.scene_index = scene_index
        await self.memory.emotional.save_state(new_emotion)

        # 6. Save episodic memory
        if output.memory_summary:
            await self.memory.episodic.add(EpisodicMemory(
                character_id=self.character_id,
                chapter_index=chapter_index,
                scene_index=scene_index,
                content=output.memory_summary,
                importance=0.6,
                involved_characters=present_character_ids,
            ))

        # 7. Update relationships
        for rc in output.relationship_changes:
            existing = await self.memory.relationships.get_with(rc.target_id)
            if existing:
                from novel_creator.models.relationship import Relationship
                updated = Relationship(
                    source_id=self.character_id,
                    target_id=rc.target_id,
                    relationship_type=existing.relationship_type,
                    trust=max(-1, min(1, existing.trust + rc.trust_delta)),
                    affection=max(-1, min(1, existing.affection + rc.affection_delta)),
                    description=rc.new_description or existing.description,
                )
                await self.memory.relationships.upsert(
                    updated,
                    chapter_index=chapter_index,
                    change_reason=rc.new_description or "scene interaction",
                )

        return actions
