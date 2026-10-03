"""Tests for the batch call routing planner."""

from __future__ import annotations

import itertools
from datetime import datetime, timedelta

import pytest

from call_router import Call, PlanResult, plan_calls


def make_call(call_id, mood=3, t=0, tiers=()):
    return Call(call_id=call_id, mood_score=mood, enqueued_at=t,
                tier_candidates=tuple(tuple(tier) for tier in tiers))


class TestRequiredScenarios:
    def test_max_connections_beat_tier1_preference(self):
        # Call 1 outranks call 2. Giving call 1 its tier-1 agent 10 would
        # leave call 2 unservable, so call 1 must take tier-2 agent 20.
        call1 = make_call(1, mood=1, t=0, tiers=([10], [20]))
        call2 = make_call(2, mood=2, t=0, tiers=([10],))
        result = plan_calls([call1, call2], [10, 20])
        assert result.assignments == {1: 20, 2: 10}
        assert result.waiting_call_ids == ()

    def test_two_tier2_beat_one_tier3(self):
        # Same connected set {1, 2} either way:
        #   plan X: 1->9 (tier2), 2->5 (tier2)   -- two tier-2, no tier-3
        #   plan Y: 1->5 (tier3), 2->9 (tier2)   -- one tier-3
        # Plan X must win even though plan Y gives the higher-priority
        # call 1 the smaller agent id (5 < 9): agent-id tie-breaking may
        # not override the upgrade-tier comparison.
        call1 = make_call(1, mood=1, t=0, tiers=([], [9], [5]))
        call2 = make_call(2, mood=2, t=0, tiers=([], [5, 9]))
        result = plan_calls([call1, call2], [5, 9])
        assert result.assignments == {1: 9, 2: 5}


class TestPriorityOrder:
    def test_lower_mood_score_wins_contested_agent(self):
        urgent = make_call(1, mood=1, t=100, tiers=([7],))
        calm = make_call(2, mood=5, t=0, tiers=([7],))
        result = plan_calls([urgent, calm], [7])
        assert result.assignments == {1: 7}
        assert result.waiting_call_ids == (2,)

    def test_earlier_wait_wins_on_score_tie(self):
        first = make_call(1, mood=2, t=0, tiers=([7],))
        later = make_call(2, mood=2, t=50, tiers=([7],))
        result = plan_calls([later, first], [7])
        assert result.assignments == {1: 7}

    def test_smaller_id_wins_on_score_and_time_tie(self):
        a = make_call(3, mood=2, t=0, tiers=([7],))
        b = make_call(8, mood=2, t=0, tiers=([7],))
        result = plan_calls([b, a], [7])
        assert result.assignments == {3: 7}

    def test_datetime_timestamps(self):
        now = datetime(2026, 10, 3, 9, 0, 0)
        early = make_call(1, mood=3, t=now, tiers=([7],))
        late = make_call(2, mood=3, t=now + timedelta(minutes=5), tiers=([7],))
        result = plan_calls([late, early], [7])
        assert result.assignments == {1: 7}


class TestConnectedSetLexicographic:
    def test_high_priority_connection_not_traded_for_two_lower(self):
        # Both plans connect 2 calls; the one connecting call 1 must win.
        high = make_call(1, mood=1, t=0, tiers=([10],))
        low1 = make_call(2, mood=5, t=0, tiers=([10, 20],))
        low2 = make_call(3, mood=5, t=1, tiers=([20],))
        result = plan_calls([high, low1, low2], [10, 20])
        assert result.assignments == {1: 10, 2: 20}
        assert result.waiting_call_ids == (3,)

    def test_unassigned_calls_keep_waiting(self):
        c1 = make_call(1, mood=1, t=0, tiers=([10],))
        c2 = make_call(2, mood=1, t=1, tiers=([10],))
        c3 = make_call(3, mood=1, t=2, tiers=([10],))
        result = plan_calls([c1, c2, c3], [10])
        assert result.assignments == {1: 10}
        assert result.waiting_call_ids == (2, 3)


class TestTierHandling:
    def test_agent_in_multiple_tiers_counts_as_lowest_tier(self):
        # Agent 10 is tier-1 and tier-3 for call 1; using it must count as
        # tier-1, so call 1 keeps 10 and call 2 takes 20.
        call1 = make_call(1, mood=1, t=0, tiers=([10], [], [10, 20]))
        call2 = make_call(2, mood=2, t=0, tiers=([10, 20],))
        result = plan_calls([call1, call2], [10, 20])
        assert result.assignments == {1: 10, 2: 20}

    def test_unavailable_agents_are_ignored(self):
        call1 = make_call(1, mood=1, t=0, tiers=([10, 30], [20]))
        result = plan_calls([call1], [20])
        assert result.assignments == {1: 20}

    def test_fewer_tiers_than_three(self):
        call1 = make_call(1, mood=1, t=0, tiers=([10],))
        result = plan_calls([call1], [10])
        assert result.assignments == {1: 10}


class TestAgentIdTieBreak:
    def test_smaller_agent_id_preferred(self):
        call1 = make_call(1, mood=1, t=0, tiers=([9, 4],))
        result = plan_calls([call1], [4, 9])
        assert result.assignments == {1: 4}

    def test_agent_ids_compared_in_call_priority_order(self):
        # Both agents tier-1 for both calls; the higher-priority call 1
        # gets the smaller id.
        call1 = make_call(1, mood=1, t=0, tiers=([4, 9],))
        call2 = make_call(2, mood=2, t=0, tiers=([4, 9],))
        result = plan_calls([call1, call2], [4, 9])
        assert result.assignments == {1: 4, 2: 9}


class TestDeterminism:
    def build(self):
        calls = [
            make_call(1, mood=1, t=5, tiers=([10], [20], [30])),
            make_call(2, mood=2, t=0, tiers=([10, 20], [30])),
            make_call(3, mood=2, t=0, tiers=([20], [40])),
            make_call(4, mood=4, t=1, tiers=([30, 40],)),
            make_call(5, mood=5, t=9, tiers=([10],)),
        ]
        agents = [10, 20, 30, 40]
        return calls, agents

    def test_input_permutation_invariance(self):
        calls, agents = self.build()
        expected = plan_calls(calls, agents)
        for perm in itertools.permutations(range(len(calls))):
            shuffled = [calls[i] for i in perm]
            for agent_perm in itertools.permutations(agents):
                result = plan_calls(shuffled, list(agent_perm))
                assert result.assignments == expected.assignments
                assert result.waiting_call_ids == expected.waiting_call_ids

    def test_repeated_computation_is_stable(self):
        calls, agents = self.build()
        first = plan_calls(calls, agents)
        for _ in range(5):
            assert plan_calls(calls, agents).assignments == first.assignments


class TestEdgeCases:
    def test_no_calls(self):
        result = plan_calls([], [10, 20])
        assert result.assignments == {}
        assert result.waiting_call_ids == ()

    def test_no_available_agents(self):
        call1 = make_call(1, mood=1, t=0, tiers=([10],))
        result = plan_calls([call1], [])
        assert result.assignments == {}
        assert result.waiting_call_ids == (1,)

    def test_call_without_candidates_waits(self):
        call1 = make_call(1, mood=1, t=0, tiers=())
        call2 = make_call(2, mood=2, t=0, tiers=([10],))
        result = plan_calls([call1, call2], [10])
        assert result.assignments == {2: 10}
        assert result.waiting_call_ids == (1,)

    def test_result_is_plan_result(self):
        result = plan_calls([], [])
        assert isinstance(result, PlanResult)


class TestValidation:
    def test_duplicate_call_id_rejected(self):
        a = make_call(1, tiers=([10],))
        b = make_call(1, tiers=([20],))
        with pytest.raises(ValueError):
            plan_calls([a, b], [10, 20])

    def test_mood_score_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            plan_calls([make_call(1, mood=0)], [])
        with pytest.raises(ValueError):
            plan_calls([make_call(1, mood=6)], [])

    def test_non_positive_ids_rejected(self):
        with pytest.raises(ValueError):
            plan_calls([make_call(0)], [])
        with pytest.raises(ValueError):
            plan_calls([make_call(1, tiers=([-3],))], [-3])
        with pytest.raises(ValueError):
            plan_calls([], [0])
