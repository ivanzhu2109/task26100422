"""规划器自动化测试。"""

import itertools
import random
from datetime import datetime, timedelta

import pytest

from call_router import Call, Snapshot, plan
from call_router.models import PlanResult

BASE = datetime(2026, 10, 3, 9, 0, 0)


def make_call(
    call_id: int,
    emotion: int = 3,
    minutes: int = 0,
    candidates: tuple[tuple[int, ...], ...] = (),
) -> Call:
    return Call(
        call_id=call_id,
        emotion=emotion,
        enqueued_at=BASE + timedelta(minutes=minutes),
        candidates=candidates,
    )


def run(calls: list[Call], agents: set[int]) -> PlanResult:
    return plan(Snapshot(calls=tuple(calls), available_agents=frozenset(agents)))


def test_required_scenario_max_count_beats_tier_preference() -> None:
    """来电1优先于来电2；不能为照顾来电1的一级偏好而少接一通。"""
    c1 = make_call(1, emotion=1, candidates=((10,), (20,)))
    c2 = make_call(2, emotion=2, candidates=((10,),))
    result = run([c1, c2], {10, 20})
    assert result.assignments == {1: 20, 2: 10}
    assert result.waiting == ()


def test_required_scenario_one_tier3_loses_to_two_tier2() -> None:
    """接通名单相同时：一个三级分配的方案输给含两个二级分配的方案；
    且坐席编号择优不能推翻升级层级比较。"""
    # 三通电话争抢坐席10（均为一级）；另各有出路：
    # 来电1 二级30，来电2 二级40，来电3 三级50。
    # 可行方案A：1->10(一级), 2->40(二级), 3->50(三级) —— 含一个三级。
    # 可行方案B：1->30(二级), 2->40(二级), 3->10(一级) —— 无三级、两个二级。
    # 方案A 中来电1拿到更小的坐席10，但层级比较优先，必须选方案B。
    c1 = make_call(1, emotion=1, candidates=((10,), (30,)))
    c2 = make_call(2, emotion=2, candidates=((10,), (40,)))
    c3 = make_call(3, emotion=3, candidates=((10,), (), (50,)))
    result = run([c1, c2, c3], {10, 30, 40, 50})
    assert result.assignments == {1: 30, 2: 40, 3: 10}
    assert result.waiting == ()


def test_priority_order_emotion_then_wait_then_id() -> None:
    """单坐席时，情绪分低者优先；同分等待久者优先；再相同编号小者优先。"""
    agents = {10}
    # 情绪分优先
    low = make_call(1, emotion=1, minutes=5, candidates=((10,),))
    high = make_call(2, emotion=4, minutes=0, candidates=((10,),))
    assert run([high, low], agents).assignments == {1: 10}
    # 同分比等待时间
    early = make_call(1, emotion=2, minutes=0, candidates=((10,),))
    late = make_call(2, emotion=2, minutes=5, candidates=((10,),))
    assert run([late, early], agents).assignments == {1: 10}
    # 时间相同比编号
    a = make_call(1, emotion=2, minutes=0, candidates=((10,),))
    b = make_call(2, emotion=2, minutes=0, candidates=((10,),))
    assert run([b, a], agents).assignments == {1: 10}


def test_connected_set_lexicographic_not_count_tradeoff() -> None:
    """不能用多个低优先级来电的偏好抵消一个高优先级来电的接通资格。"""
    # 高优先级来电1占任一坐席都会挤掉一通低优先级来电；
    # 但接通名单比较是逐通字典序，{1,2} 必须胜过 {2,3}。
    c1 = make_call(1, emotion=1, candidates=((10, 20),))
    c2 = make_call(2, emotion=5, candidates=((10,),))
    c3 = make_call(3, emotion=5, candidates=((20,),))
    result = run([c3, c2, c1], {10, 20})
    # 最多接两通；必须包含来电1，且来电1拿坐席20（否则来电2无法接通）
    assert result.assignments == {1: 20, 2: 10}
    assert result.waiting == (3,)


def test_same_agent_multiple_tiers_counts_lowest() -> None:
    """同一坐席出现在多个层级时按最低层级计算。"""
    c1 = make_call(1, emotion=1, candidates=((), (10,), (10,)))
    c2 = make_call(2, emotion=2, candidates=((10,),))
    # 坐席10对来电1是二级；若误判为三级，来电1会被挤到等待
    result = run([c1, c2], {10, 20})
    assert result.assignments[1] in (10, 20)
    # 更直接：单来电单坐席，多层级重复，应接通且按二级计入
    only = make_call(1, emotion=1, candidates=((), (10,), (10,)))
    assert run([only], {10}).assignments == {1: 10}


def test_unavailable_agents_excluded() -> None:
    """只能使用候选名单中且当前可用的坐席。"""
    c1 = make_call(1, emotion=1, candidates=((10,), (20,)))
    result = run([c1], {20})
    assert result.assignments == {1: 20}
    assert run([c1], {99}).assignments == {}
    assert run([c1], {99}).waiting == (1,)


def test_agent_id_tiebreak_by_call_priority() -> None:
    """其余条件相同时，高优先级来电先获得更小的坐席编号。"""
    c1 = make_call(1, emotion=1, candidates=((10, 20),))
    c2 = make_call(2, emotion=2, candidates=((10, 20),))
    result = run([c1, c2], {10, 20})
    assert result.assignments == {1: 10, 2: 20}


def test_determinism_regardless_of_input_order() -> None:
    """相同快照重复计算或改变输入排列顺序，结果一致。"""
    calls = [
        make_call(1, emotion=1, minutes=2, candidates=((10,), (30,))),
        make_call(2, emotion=1, minutes=1, candidates=((10, 20),)),
        make_call(3, emotion=2, minutes=0, candidates=((20,), (30,), (40,))),
        make_call(4, emotion=5, minutes=9, candidates=((40,),)),
    ]
    agents = {10, 20, 30, 40}
    baseline = run(calls, agents)
    assert run(list(reversed(calls)), agents) == baseline
    assert run([calls[2], calls[0], calls[3], calls[1]], agents) == baseline
    assert run(calls, agents) == baseline


def test_no_candidates_waits() -> None:
    """没有候选或候选全不可用的来电继续等待。"""
    c1 = make_call(1, emotion=1, candidates=())
    c2 = make_call(2, emotion=1, candidates=((10,),))
    result = run([c1, c2], set())
    assert result.assignments == {}
    assert result.waiting == (1, 2)


def test_empty_snapshot() -> None:
    result = run([], set())
    assert result.assignments == {}
    assert result.waiting == ()


def test_validation() -> None:
    with pytest.raises(ValueError):
        make_call(0)
    with pytest.raises(ValueError):
        make_call(1, emotion=0)
    with pytest.raises(ValueError):
        make_call(1, emotion=6)
    with pytest.raises(ValueError):
        make_call(1, candidates=((1,), (2,), (3,), (4,)))
    with pytest.raises(ValueError):
        make_call(1, candidates=((-5,),))
    with pytest.raises(ValueError):
        run([make_call(1), make_call(1)], set())


def brute_force_best(calls: list[Call], agents: set[int]) -> dict[int, int]:
    """暴力枚举全部可行分配，按完整目标元组取最优（用于对拍）。"""
    ordered = sorted(calls, key=Call.priority_key)
    agent_list = sorted(agents)
    best_key: tuple | None = None
    best_assignment: dict[int, int] = {}
    # 每通来电：候选坐席（可用）按最低层级
    options = []
    for call in ordered:
        tiers = {
            a: t for a, t in call.agent_tiers().items() if a in agents
        }
        options.append(tiers)
    # 枚举每通来电：不接通或接通某个候选坐席
    choice_space = [[None] + sorted(tiers) for tiers in options]
    for combo in itertools.product(*choice_space):
        used = [c for c in combo if c is not None]
        if len(set(used)) != len(used):
            continue
        connected = [c is not None for c in combo]
        t3 = sum(
            1 for i, c in enumerate(combo) if c is not None and options[i][c] == 3
        )
        t2 = sum(
            1 for i, c in enumerate(combo) if c is not None and options[i][c] == 2
        )
        key = (
            -sum(connected),
            tuple(0 if ok else 1 for ok in connected),
            t3,
            t2,
            tuple(c for c in combo if c is not None),
        )
        if best_key is None or key < best_key:
            best_key = key
            best_assignment = {
                call.call_id: c for call, c in zip(ordered, combo) if c is not None
            }
    return best_assignment


def test_randomized_against_brute_force() -> None:
    """小规模随机实例与暴力枚举对拍。"""
    rng = random.Random(20261003)
    for _ in range(300):
        num_calls = rng.randint(0, 4)
        agent_pool = rng.sample(range(1, 8), rng.randint(0, 5))
        calls = []
        for cid in range(1, num_calls + 1):
            tiers = []
            for _ in range(rng.randint(0, 3)):
                tiers.append(tuple(rng.sample(agent_pool, rng.randint(0, len(agent_pool)))))
            calls.append(
                make_call(
                    cid,
                    emotion=rng.randint(1, 5),
                    minutes=rng.randint(0, 3),
                    candidates=tuple(tiers),
                )
            )
        agents = set(a for a in agent_pool if rng.random() < 0.8)
        expected = brute_force_best(calls, agents)
        assert run(calls, agents).assignments == expected
