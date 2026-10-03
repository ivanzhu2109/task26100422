"""Cross-check the planner against exhaustive enumeration on small cases."""

from __future__ import annotations

import itertools
import random

from call_router import Call, plan_calls


def priority_key(call):
    return (call.mood_score, call.enqueued_at, call.call_id)


def best_tiers(call, agents):
    best = {}
    for tier_index, tier in enumerate(call.tier_candidates, start=1):
        for agent_id in tier:
            if agent_id in agents and agent_id not in best:
                best[agent_id] = tier_index
    return best


def brute_force(calls, agents):
    ordered = sorted(calls, key=priority_key)
    usable = [best_tiers(c, agents) for c in ordered]
    best_key = None
    best_assignment = {}
    # Enumerate every partial injective assignment call -> agent.
    for assignment in itertools.product(*([None] + sorted(u) for u in usable)):
        used = [a for a in assignment if a is not None]
        if len(set(used)) != len(used):
            continue
        connected = tuple(0 if a is None else 1 for a in assignment)
        tiers = [usable[i][a] for i, a in enumerate(assignment) if a is not None]
        agent_ids = tuple(a for a in assignment if a is not None)
        key = (
            -sum(connected),
            tuple(-c for c in connected),
            sum(1 for t in tiers if t >= 3),
            sum(1 for t in tiers if t == 2),
            agent_ids,
        )
        if best_key is None or key < best_key:
            best_key = key
            best_assignment = {
                ordered[i].call_id: a for i, a in enumerate(assignment) if a is not None
            }
    return best_assignment


def random_case(rng):
    agent_pool = rng.sample(range(1, 15), k=rng.randint(1, 5))
    calls = []
    for call_id in rng.sample(range(1, 30), k=rng.randint(0, 5)):
        tiers = []
        for _ in range(rng.randint(0, 3)):
            tiers.append(tuple(rng.sample(range(1, 15), k=rng.randint(0, 4))))
        calls.append(Call(call_id=call_id,
                          mood_score=rng.randint(1, 5),
                          enqueued_at=rng.randint(0, 20),
                          tier_candidates=tuple(tiers)))
    return calls, agent_pool


def test_matches_brute_force_on_random_small_cases():
    rng = random.Random(20261003)
    for _ in range(300):
        calls, agents = random_case(rng)
        expected = brute_force(calls, agents)
        result = plan_calls(calls, agents)
        assert result.assignments == expected, (
            f"calls={calls!r} agents={agents!r} "
            f"got={result.assignments} want={expected}"
        )
