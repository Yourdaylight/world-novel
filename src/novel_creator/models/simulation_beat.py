"""SimulationBeat — the atomic timeline event for decoupled simulation."""

from __future__ import annotations

from pydantic import BaseModel, Field

from novel_creator.models.story import SceneBeat


class SimulationBeat(BaseModel):
    """A single beat on the story timeline, independent of any chapter.

    Beats are the atomic unit of simulation.  They live in the
    ``simulation_beats`` table and are consumed by the Simulation Graph.
    The Writer reads completed beats (via ``beat_range``) to compose
    chapters freely.
    """

    beat_id: str = Field(description="唯一标识, e.g. 'beat_001'")
    sequence: int = Field(description="全局排序号 (0-based)")
    story_time: str = Field(default="", description="故事世界中的时间标记, e.g. '第三日 午后'")
    era_id: str = Field(default="", description="所属时代ID")
    location: str = Field(description="发生地点")
    involved_characters: list[str] = Field(
        default_factory=list, description="参与角色ID列表",
    )
    objective: str = Field(description="本 beat 要推进的剧情目标")
    conflict: str = Field(default="", description="冲突或张力")
    tone: str = Field(default="neutral", description="情绪基调")
    status: str = Field(
        default="pending",
        description="pending → simulating → completed",
    )
    suggested_chapter: int | None = Field(
        default=None,
        description="建议归入哪章 (writer 可覆盖)",
    )
    parallel_group: str | None = Field(
        default=None,
        description="同组 beat 可并行模拟 (不同地点同一时间)",
    )
    foreshadows_to_plant: list[str] = Field(
        default_factory=list, description="需要埋设的伏笔ID列表",
    )
    foreshadows_to_payoff: list[str] = Field(
        default_factory=list, description="需要回收的伏笔ID列表",
    )

    # ------------------------------------------------------------------
    # Adapter
    # ------------------------------------------------------------------

    def to_scene_beat(self) -> SceneBeat:
        """Convert to :class:`SceneBeat` for :class:`SceneOrchestrator` compatibility.

        The ``scene_index`` is derived from ``sequence`` so that existing
        orchestration code can work unchanged.
        """
        return SceneBeat(
            scene_index=self.sequence,
            location=self.location,
            involved_characters=self.involved_characters,
            objective=self.objective,
            conflict=self.conflict,
            tone=self.tone,
            foreshadows_to_plant=self.foreshadows_to_plant,
            foreshadows_to_payoff=self.foreshadows_to_payoff,
        )
