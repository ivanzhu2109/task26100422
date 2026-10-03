"""Data types shared between the caller system and the routing planner."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Union

# A wait-queue timestamp: epoch seconds (int/float) or a datetime.
WaitTimestamp = Union[int, float, datetime]


@dataclass(frozen=True)
class Call:
    """A single inbound call waiting to be answered.

    Attributes:
        call_id: Unique positive integer identifier.
        mood_score: Emotion score in [1, 5]; lower means higher priority.
        enqueued_at: When the call started waiting; earlier means higher priority.
        tier_candidates: Candidate agent ids grouped by tier, best tier first.
            ``tier_candidates[0]`` is tier 1, ``tier_candidates[1]`` tier 2, etc.
            An agent appearing in several tiers counts as its lowest tier number.
    """

    call_id: int
    mood_score: int
    enqueued_at: WaitTimestamp
    tier_candidates: tuple[tuple[int, ...], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PlanResult:
    """Outcome of one planning round.

    Attributes:
        assignments: Mapping of connected ``call_id -> agent_id``.
        waiting_call_ids: Ids of calls that remain waiting, in priority order.
    """

    assignments: dict[int, int]
    waiting_call_ids: tuple[int, ...]
