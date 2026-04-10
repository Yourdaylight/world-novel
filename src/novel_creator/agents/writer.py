"""Writer Agent — transforms character actions into literary narrative."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from langchain_core.prompts import ChatPromptTemplate

from novel_creator.llm import get_llm, invoke_with_retry, stream_with_retry
from novel_creator.models.memory import CharacterAction
from novel_creator.models.narrative import Scene

SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "writer.md").read_text()


class WriterAgent:
    def __init__(self):
        self.llm = get_llm("writer")

    async def write_scene(
        self,
        chapter_index: int,
        scene_index: int,
        location: str,
        character_actions: list[CharacterAction] | None = None,
        character_profiles: dict[str, str] | None = None,
        previous_context: str = "",
        *,
        scene_objective: str = "",
        world_context: str = "",
        location_description: str = "",
        foreshadow_instructions: str = "",
        god_context: str = "",
        director_intent: str = "",
        scene_transcript=None,
        word_count_target: int = 1500,
        chapter_timeline: str = "",
    ) -> Scene:
        """Write a literary scene based on character actions / timeline.

        Parameters
        ----------
        scene_objective : str
            What the scene should achieve (legacy parameter).
        director_intent : str
            V5+ director's intent for the scene (overrides scene_objective).
        scene_transcript : SceneResult, optional
            V5+ full scene simulation transcript (turns, opening decisions).
        word_count_target : int
            Target word count for this scene.
        chapter_timeline : str
            V9+ full chapter timeline text for decoupled writing.
        """
        character_actions = character_actions or []
        character_profiles = character_profiles or {}

        # Prefer director_intent over scene_objective
        objective = director_intent or scene_objective or "推进剧情"

        # Build actions description
        actions_text = self._format_actions(character_actions)
        profiles_text = "\n".join(f"- {cid}: {desc}" for cid, desc in character_profiles.items())

        # Build optional blocks
        extra_blocks = ""
        if world_context:
            extra_blocks += f"## 世界观背景\n{world_context}\n\n"
        if location_description:
            extra_blocks += f"## 地点描写参考\n{location_description}\n\n"
        if foreshadow_instructions:
            extra_blocks += f"## 伏笔指令\n{foreshadow_instructions}\n\n"
        if god_context:
            extra_blocks += f"## 命运之手\n以下是命运的安排，请自然融入叙事中:\n{god_context}\n\n"

        # V5: Scene transcript block (rich simulation data)
        transcript_block = ""
        if scene_transcript:
            try:
                parts = []
                if scene_transcript.opening_decisions:
                    parts.append("**角色开场心态：**")
                    for cid, d in scene_transcript.opening_decisions.items():
                        parts.append(f"- {cid}: 判断「{d.current_assessment}」→ 渴望「{d.personal_desire}」→ 策略「{d.chosen_approach}」({d.emotional_drive})")
                    parts.append("")
                for turn in scene_transcript.turns:
                    vis = "（内心）" if not turn.is_visible else ""
                    tgt = f" → {turn.target_id}" if turn.target_id else ""
                    parts.append(f"  {turn.turn_index + 1}. [{turn.character_id}] {turn.turn_type.value}{tgt}{vis}: {turn.content}")
                transcript_block = f"## 场景模拟记录\n" + "\n".join(parts) + "\n\n"
            except Exception:
                pass

        # V9: Chapter timeline block (decoupled pipeline)
        timeline_block = ""
        if chapter_timeline:
            timeline_block = f"## 角色行动时间线\n{chapter_timeline}\n\n"

        # Use the richest source: timeline > transcript > actions
        source_block = timeline_block or transcript_block or (f"## 角色行动记录\n{actions_text}\n\n" if actions_text else "")

        word_instruction = f"请撰写约{word_count_target}字的文学叙事。" if word_count_target else "请撰写800-1500字的文学叙事。"

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", (
                f"## 场景信息\n"
                f"**章节**: 第{chapter_index + 1}章\n"
                f"**场景**: 第{scene_index + 1}个场景\n"
                f"**地点**: {location}\n"
                f"**导演意图**: {objective}\n\n"
                f"## 角色简介\n{profiles_text}\n\n"
                f"{source_block}"
                f"{extra_blocks}"
                f"{'## 前文概要' + chr(10) + previous_context + chr(10) + chr(10) if previous_context else ''}"
                f"{word_instruction}"
                "要求: 语言优美、叙事流畅、人物鲜活。直接输出散文文本。"
            )),
        ])
        chain = prompt | self.llm
        response = await invoke_with_retry(
            chain, {}, description=f"Write scene ch{chapter_index+1} s{scene_index+1}",
            role="writer", chapter_index=chapter_index,
        )
        content = response.content if hasattr(response, "content") else str(response)

        # Determine POV character (character with most actions)
        action_counts: dict[str, int] = {}
        for a in character_actions:
            action_counts[a.character_id] = action_counts.get(a.character_id, 0) + 1
        pov = max(action_counts, key=action_counts.get) if action_counts else ""

        return Scene(
            scene_index=scene_index,
            content=content,
            pov_character=pov,
        )

    async def write_scene_streaming(
        self,
        chapter_index: int,
        scene_index: int,
        location: str,
        scene_objective: str,
        character_actions: list[CharacterAction],
        character_profiles: dict[str, str],
        previous_context: str = "",
        *,
        world_context: str = "",
        location_description: str = "",
        foreshadow_instructions: str = "",
        god_context: str = "",
        on_token: Callable[[str], None] | None = None,
    ) -> Scene:
        """Stream-write a scene, calling on_token for each chunk.

        Falls back to non-streaming write_scene if streaming fails.
        """
        # Build actions description
        actions_text = self._format_actions(character_actions)
        profiles_text = "\n".join(f"- {cid}: {desc}" for cid, desc in character_profiles.items())

        # Build optional blocks
        extra_blocks = ""
        if world_context:
            extra_blocks += f"## 世界观背景\n{world_context}\n\n"
        if location_description:
            extra_blocks += f"## 地点描写参考\n{location_description}\n\n"
        if foreshadow_instructions:
            extra_blocks += f"## 伏笔指令\n{foreshadow_instructions}\n\n"
        if god_context:
            extra_blocks += f"## 命运之手\n以下是命运的安排，请自然融入叙事中:\n{god_context}\n\n"

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", (
                f"## 场景信息\n"
                f"**章节**: 第{chapter_index + 1}章\n"
                f"**场景**: 第{scene_index + 1}个场景\n"
                f"**地点**: {location}\n"
                f"**场景目标**: {scene_objective}\n\n"
                f"## 角色简介\n{profiles_text}\n\n"
                f"## 角色行动记录\n{actions_text}\n\n"
                f"{extra_blocks}"
                f"{'## 前文概要' + chr(10) + previous_context + chr(10) + chr(10) if previous_context else ''}"
                "请基于以上角色的行动、对话和内心世界，撰写 800-1500 字的文学叙事。"
                "要求: 语言优美、叙事流畅、人物鲜活。注意字数要求。直接输出散文文本。"
            )),
        ])

        chain = prompt | self.llm
        chunks: list[str] = []

        try:
            async for chunk in stream_with_retry(
                chain, {},
                description=f"Stream scene ch{chapter_index+1} s{scene_index+1}",
            ):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                chunks.append(token)
                if on_token:
                    await on_token(token)
        except Exception:
            # Fallback to non-streaming
            return await self.write_scene(
                chapter_index, scene_index, location, scene_objective,
                character_actions, character_profiles, previous_context,
                world_context=world_context, location_description=location_description,
                foreshadow_instructions=foreshadow_instructions, god_context=god_context,
            )

        content = "".join(chunks)

        # Determine POV character
        action_counts: dict[str, int] = {}
        for a in character_actions:
            action_counts[a.character_id] = action_counts.get(a.character_id, 0) + 1
        pov = max(action_counts, key=action_counts.get) if action_counts else ""

        return Scene(
            scene_index=scene_index,
            content=content,
            pov_character=pov,
        )

    def _format_actions(self, actions: list[CharacterAction]) -> str:
        parts: list[str] = []
        type_labels = {
            "dialogue": "💬 对话",
            "behavior": "🎬 行为",
            "thought": "💭 内心",
            "reaction": "⚡ 反应",
        }
        for a in actions:
            label = type_labels.get(a.action_type.value, a.action_type.value)
            target = f" → {a.target_character_id}" if a.target_character_id else ""
            parts.append(f"[{a.character_id}] {label}{target}: {a.content}")
        return "\n".join(parts)

    async def write_chapter_summary(self, chapter_text: str) -> str:
        """Generate a brief summary of a chapter for context continuity."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一位小说编辑，请用100-200字概括以下章节内容，重点关注情节推进和人物关系变化。"),
            ("human", "{text}"),
        ])
        chain = prompt | self.llm
        response = await invoke_with_retry(
            chain, {"text": chapter_text[:3000]},
            description="Write chapter summary",
            role="writer",
        )
        return response.content if hasattr(response, "content") else str(response)
