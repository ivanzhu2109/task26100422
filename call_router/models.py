"""数据模型：来电、候选名单、规划快照与结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Call:
    """一通等待接听的来电。

    candidates 为三级候选名单：candidates[0] 为一级（最优先），
    candidates[1] 为二级，candidates[2] 为三级（升级）。
    同一坐席出现在多个层级时按最低层级计算。
    """

    call_id: int
    emotion: int
    enqueued_at: datetime
    candidates: tuple[tuple[int, ...], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.call_id, int) or self.call_id <= 0:
            raise ValueError(f"call_id 必须为正整数: {self.call_id!r}")
        if not 1 <= self.emotion <= 5:
            raise ValueError(f"emotion 必须在 1..5: {self.emotion!r}")
        if len(self.candidates) > 3:
            raise ValueError("候选名单最多三级")
        for tier in self.candidates:
            for agent_id in tier:
                if not isinstance(agent_id, int) or agent_id <= 0:
                    raise ValueError(f"坐席编号必须为正整数: {agent_id!r}")

    def priority_key(self) -> tuple[int, datetime, int]:
        """优先级排序键：情绪分数低者优先，其次等待早者，其次编号小者。"""
        return (self.emotion, self.enqueued_at, self.call_id)

    def agent_tiers(self) -> dict[int, int]:
        """候选坐席 -> 层级（1 为一级）。同一坐席多次出现时取最低层级。"""
        tiers: dict[int, int] = {}
        for index, tier in enumerate(self.candidates, start=1):
            for agent_id in tier:
                if agent_id not in tiers:
                    tiers[agent_id] = index
        return tiers


@dataclass(frozen=True)
class Snapshot:
    """一次规划的输入快照：待分配来电 + 当前可用坐席编号集合。"""

    calls: tuple[Call, ...]
    available_agents: frozenset[int]

    def __post_init__(self) -> None:
        seen: set[int] = set()
        for call in self.calls:
            if call.call_id in seen:
                raise ValueError(f"来电编号重复: {call.call_id}")
            seen.add(call.call_id)
        for agent_id in self.available_agents:
            if not isinstance(agent_id, int) or agent_id <= 0:
                raise ValueError(f"坐席编号必须为正整数: {agent_id!r}")


@dataclass(frozen=True)
class PlanResult:
    """规划结果：assignments 为 来电编号 -> 坐席编号；waiting 为未接通来电编号（升序）。"""

    assignments: dict[int, int]
    waiting: tuple[int, ...]
