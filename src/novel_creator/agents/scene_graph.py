"""Scene Graph — multi-character scene orchestrator.

Runs a multi-turn dialogue simulation where each character agent
independently decides actions, forming a turn-by-turn transcript.

Usage (from graph nodes):
    orchestrator = SceneGraph(agents=..., scene_beat=..., ...)
    result: SceneResult = await orchestrator.run()
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from novel_creator.agents.character import CharacterAgent
from novel_creator.llm import get_llm, invoke_with_retry
from novel_creator.models.memory import ActionType, CharacterAction
from novel_creator.models.scene_turn import (
    OpeningDecision,
    SceneResult,
    SceneTurn,
    TurnType,
)

logger = logging.getLogger("novel_creator.agents.scene_graph")

# Maximum turns before forcing scene end
MAX_TURNS = 30
# Minimum turns so scenes aren't too short
MIN_TURNS = 4


class SceneGraph:
    """Orchestrate a scene simulation among multiple character agents.

    Each round:
      1. Pick an active character (round-robin or LLM-selected)
      2. Character decides action (say/do/think/feel/leave)
      3. Record turn
      4. Check termination conditions

    Parameters
    ----------
    agents : dict[str, CharacterAgent]
        Character agents participating in this scene.
    scene_beat : SceneBeat
        Scene definition (location, objective, involved_characters).
    chapter_index, scene_index : int
        Current position in the story.
    world_context : str
        World description for character prompts.
    location_detail : str
        Location details.
    timeline : StoryTimeline | None
        For era-aware memory.
    char_name_map : dict[str, str]
        character_id → display name.
    """

    def __init__(
        self,
        agents: dict[str, CharacterAgent],
        scene_beat,
        chapter_index: int,
        scene_index: int,
        world_context: str = "",
        location_detail: str = "",
        timeline=None,
        char_name_map: dict[str, str] | None = None,
    ):
        self.agents = agents
        self.scene_beat = scene_beat
        self.chapter_index = chapter_index
        self.scene_index = scene_index
        self.world_context = world_context
        self.location_detail = location_detail
        self.timeline = timeline
        self.char_name_map = char_name_map or {}

        self._turns: list[SceneTurn] = []
        self._all_actions: list[CharacterAction] = []
        self._opening_decisions: dict[str, OpeningDecision] = {}
        self._active_characters: list[str] = list(agents.keys())

    async def run(self) -> SceneResult:
        """Execute the scene simulation and return the result."""
        try:
            # Phase 1: Opening decisions — each character assesses the situation
            await self._opening_phase()

            # Phase 2: Multi-turn interaction
            ended_by = await self._interaction_phase()

            return SceneResult(
                turns=self._turns,
                character_actions=self._all_actions,
                opening_decisions=self._opening_decisions,
                total_turns=len(self._turns),
                ended_by=ended_by,
            )
        except Exception as e:
            logger.error("Scene simulation error: %s", e)
            return SceneResult(
                turns=self._turns,
                character_actions=self._all_actions,
                opening_decisions=self._opening_decisions,
                total_turns=len(self._turns),
                ended_by=f"error: {e}",
            )

    async def _opening_phase(self) -> None:
        """Each character makes an opening decision about the scene."""
        for cid in self._active_characters:
            try:
                agent = self.agents[cid]
                profile = await agent.memory.get_profile()
                name = profile.name if profile else cid

                # Simple opening: ask the character how they assess the scene
                llm = get_llm("character", temperature=0.8)

                from pydantic import BaseModel, Field

                class _OpeningOutput(BaseModel):
                    assessment: str = Field(description="对当前场景的判断")
                    desire: str = Field(description="最想达成的目标")
                    approach: str = Field(description="打算采取的策略")
                    emotional_drive: str = Field(description="驱动行为的情绪")

                memory_ctx = await agent.memory.get_context_window(
                    self.chapter_index, self.scene_index, timeline=self.timeline,
                )

                from langchain_core.prompts import ChatPromptTemplate
                prompt = ChatPromptTemplate.from_messages([
                    ("system", (
                        f"你是{name}。以下是你的记忆和身份：\n{memory_ctx}\n\n"
                        f"世界背景：{self.world_context}\n"
                        f"当前地点：{self.scene_beat.location}\n"
                        f"场景目标：{self.scene_beat.objective}\n"
                    )),
                    ("human", "你刚到达这个场景。简短评估当前状况，你最想做什么，以及你的策略。"),
                ])

                chain = prompt | llm.with_structured_output(_OpeningOutput)
                result = await invoke_with_retry(
                    chain, {},
                    description=f"Opening decision for {cid}",
                    role="character", chapter_index=self.chapter_index,
                )
                self._opening_decisions[cid] = OpeningDecision(
                    current_assessment=result.assessment,
                    personal_desire=result.desire,
                    chosen_approach=result.approach,
                    emotional_drive=result.emotional_drive,
                )
            except Exception as e:
                logger.warning("Opening decision failed for %s: %s", cid, e)
                self._opening_decisions[cid] = OpeningDecision(
                    current_assessment="（无法评估）",
                    personal_desire="（未知）",
                    chosen_approach="观察",
                    emotional_drive="平静",
                )

    async def _interaction_phase(self) -> str:
        """Multi-turn interaction loop. Returns the termination reason."""
        turn_index = 0

        while turn_index < MAX_TURNS and self._active_characters:
            # Round-robin: pick the next character
            char_idx = turn_index % len(self._active_characters)
            cid = self._active_characters[char_idx]

            try:
                agent = self.agents[cid]
                # Get other characters' recent visible actions
                recent_others = [
                    a for a in self._all_actions[-10:]
                    if a.character_id != cid
                ]
                actions = await agent.process_scene(
                    chapter_index=self.chapter_index,
                    scene_index=self.scene_index,
                    location=self.scene_beat.location,
                    scene_objective=self.scene_beat.objective,
                    present_character_ids=self._active_characters,
                    other_actions=recent_others,
                    world_context=self.world_context,
                    location_detail=self.location_detail,
                    timeline=self.timeline,
                )

                # Convert actions to turns
                for action in actions:
                    turn_type = _action_type_to_turn_type(action.action_type)
                    is_visible = turn_type not in (TurnType.THINK, TurnType.FEEL)

                    self._turns.append(SceneTurn(
                        turn_index=turn_index,
                        character_id=cid,
                        turn_type=turn_type,
                        content=action.content,
                        target_id=action.target_character_id,
                        is_visible=is_visible,
                        emotional_shift=action.emotional_shift or {},
                        location=self.scene_beat.location,
                    ))
                    turn_index += 1

                self._all_actions.extend(actions)

                # Check if character left
                if any(a.action_type == ActionType.BEHAVIOR and "离开" in a.content for a in actions):
                    self._active_characters = [c for c in self._active_characters if c != cid]
                    self._turns.append(SceneTurn(
                        turn_index=turn_index,
                        character_id=cid,
                        turn_type=TurnType.LEAVE,
                        content=f"{self.char_name_map.get(cid, cid)}离开了场景",
                        is_visible=True,
                        location=self.scene_beat.location,
                    ))
                    turn_index += 1

            except Exception as e:
                logger.error("Turn failed for %s: %s", cid, e)
                turn_index += 1

            # Natural end: enough turns and objective likely met
            if turn_index >= MIN_TURNS and turn_index >= len(self._active_characters) * 3:
                # If we've had at least 3 rounds per character, check for natural end
                if turn_index >= MAX_TURNS:
                    return "max_turns"

        if not self._active_characters:
            return "all_left"

        return "natural"


def _action_type_to_turn_type(action_type: ActionType) -> TurnType:
    """Map CharacterAction action_type to SceneTurn turn_type."""
    mapping = {
        ActionType.DIALOGUE: TurnType.SAY,
        ActionType.BEHAVIOR: TurnType.DO,
        ActionType.THOUGHT: TurnType.THINK,
        ActionType.REACTION: TurnType.FEEL,
    }
    return mapping.get(action_type, TurnType.DO)
