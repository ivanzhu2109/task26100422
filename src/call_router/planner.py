"""Batch routing planner: assigns waiting calls to available agents.

The lexicographic objectives are folded into one big-integer edge cost and
solved with a single min-cost max-flow:

* objective 1 (connected count) is enforced by requiring the max-flow value;
* objective 2 (which calls connect) uses superincreasing per-call bonuses
  ``B ** (n - 1 - rank)`` so no group of lower-priority calls can outweigh
  a higher-priority one;
* objective 3 (tier usage) adds penalties ``(n + 1) ** (tier - 2)`` scaled to
  dominate objective 4 but stay below any single call bonus;
* objective 4 (agent ids) adds ``agent_id * B ** (n - 1 - rank)``, a base-B
  encoding of the agent-id sequence in call-priority order.

Because every objective level strictly dominates the sum of all lower levels,
the minimum-cost flow is the unique optimum and does not depend on input
ordering.
"""

from __future__ import annotations

from datetime import datetime
from typing import Collection, Sequence

from ._flow import max_flow_value, min_cost_flow
from .models import Call, PlanResult


def _validate(calls: Sequence[Call], available_agents: Collection[int]) -> set[int]:
    seen_ids: set[int] = set()
    for call in calls:
        if isinstance(call.call_id, bool) or not isinstance(call.call_id, int) or call.call_id <= 0:
            raise ValueError(f"call_id must be a positive integer, got {call.call_id!r}")
        if call.call_id in seen_ids:
            raise ValueError(f"duplicate call_id {call.call_id}")
        seen_ids.add(call.call_id)
        if isinstance(call.mood_score, bool) or not isinstance(call.mood_score, int) \
                or not 1 <= call.mood_score <= 5:
            raise ValueError(f"mood_score must be an integer in [1, 5], got {call.mood_score!r}")
        if isinstance(call.enqueued_at, bool) or not isinstance(call.enqueued_at, (int, float, datetime)):
            raise ValueError(f"enqueued_at must be a number or datetime, got {call.enqueued_at!r}")
        for tier in call.tier_candidates:
            for agent_id in tier:
                if isinstance(agent_id, bool) or not isinstance(agent_id, int) or agent_id <= 0:
                    raise ValueError(f"agent id must be a positive integer, got {agent_id!r}")
    agents: set[int] = set()
    for agent_id in available_agents:
        if isinstance(agent_id, bool) or not isinstance(agent_id, int) or agent_id <= 0:
            raise ValueError(f"agent id must be a positive integer, got {agent_id!r}")
        agents.add(agent_id)
    return agents


def _tier_penalty(tier: int, num_calls: int) -> int:
    """Penalty for using a candidate of ``tier`` (1-based)."""
    if tier <= 1:
        return 0
    return (num_calls + 1) ** (tier - 2)


def plan_calls(calls: Sequence[Call], available_agents: Collection[int]) -> PlanResult:
    """Plan one batch of waiting calls against the current agent snapshot.

    Objectives, applied lexicographically:
        1. Maximise the number of connected calls.
        2. Prefer connecting higher-priority calls (mood score, then wait
           time, then call id).
        3. Minimise tier-3 assignments, then tier-2 assignments.
        4. For connected calls in priority order, prefer smaller agent ids.

    The result is deterministic and independent of input ordering.
    """
    agents = _validate(calls, available_agents)
    ordered = sorted(calls, key=lambda c: (c.mood_score, c.enqueued_at, c.call_id))
    n = len(ordered)

    # Best (lowest) tier per candidate agent, restricted to available agents.
    usable: list[dict[int, int]] = []
    for call in ordered:
        best_tier: dict[int, int] = {}
        for tier_index, tier in enumerate(call.tier_candidates, start=1):
            for agent_id in tier:
                if agent_id in agents and agent_id not in best_tier:
                    best_tier[agent_id] = tier_index
        usable.append(best_tier)

    connected: dict[int, int] = {}
    candidate_agents = sorted({a for tiers in usable for a in tiers})
    if n and candidate_agents:
        base = candidate_agents[-1] + 1  # superincreasing base, > any agent id
        max_tier = max((t for tiers in usable for t in tiers.values()), default=1)
        agent_scale = (candidate_agents[-1] * base ** n) + 1
        call_scale = (n * _tier_penalty(max_tier, n) + 1) * agent_scale

        source = 0
        call_node = {i: 1 + i for i in range(n)}
        agent_node = {a: 1 + n + i for i, a in enumerate(candidate_agents)}
        sink = 1 + n + len(candidate_agents)

        edges: list[tuple[int, int, int, int]] = []
        call_edge_owner: list[int] = []  # edge index -> call rank, for call->agent arcs
        for i in range(n):
            edges.append((source, call_node[i], 1, 0))
        for i in range(n):
            bonus = base ** (n - 1 - i)
            for agent_id in sorted(usable[i]):
                tier = usable[i][agent_id]
                cost = -bonus * call_scale \
                    + _tier_penalty(tier, n) * agent_scale \
                    + agent_id * bonus
                call_edge_owner.append(i)
                edges.append((call_node[i], agent_node[agent_id], 1, cost))
        first_call_edge = n
        for agent_id in candidate_agents:
            edges.append((agent_node[agent_id], sink, 1, 0))

        flow_value = max_flow_value(sink + 1, edges, source, sink)
        flows = min_cost_flow(sink + 1, edges, source, sink, flow_value)
        for offset, edge_index in enumerate(range(first_call_edge, first_call_edge + len(call_edge_owner))):
            if flows[edge_index] == 1:
                _, v, _, _ = edges[edge_index]
                agent_id = candidate_agents[v - 1 - n]
                connected[ordered[call_edge_owner[offset]].call_id] = agent_id

    waiting = tuple(c.call_id for c in ordered if c.call_id not in connected)
    return PlanResult(assignments=connected, waiting_call_ids=waiting)
