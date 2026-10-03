"""批量路由规划器：对快照计算确定性的最优分配方案。"""

from __future__ import annotations

from .matching import max_matching_size, min_cost_flow
from .models import Call, PlanResult, Snapshot


class _Workspace:
    """一次规划期间的归一化数据（输入快照保持不变，与输入顺序无关）。"""

    def __init__(self, snapshot: Snapshot) -> None:
        self.calls: list[Call] = sorted(snapshot.calls, key=Call.priority_key)
        self.available: frozenset[int] = snapshot.available_agents
        # 每通来电：可用候选坐席（升序）与坐席层级
        self.adjacency: dict[int, list[int]] = {}
        self.tiers: dict[int, dict[int, int]] = {}
        for call in self.calls:
            tier_map = {
                agent: tier
                for agent, tier in call.agent_tiers().items()
                if agent in self.available
            }
            self.tiers[call.call_id] = tier_map
            self.adjacency[call.call_id] = sorted(tier_map)

    def tier_cost(self, call_id: int, agent_id: int, big: int) -> int:
        tier = self.tiers[call_id][agent_id]
        if tier == 3:
            return big
        if tier == 2:
            return 1
        return 0

    def min_upgrade_cost(
        self,
        call_ids: list[int],
        excluded_agents: set[int],
        big: int,
    ) -> tuple[int, int] | None:
        """将指定来电全部接通的最小升级费用（流量, 费用）；不可行返回 None。"""
        agents = sorted(self.available - excluded_agents)
        # 节点编号：0=源，1..n=来电，其后为坐席，最后=汇
        n = len(call_ids)
        agent_node = {a: 1 + n + i for i, a in enumerate(agents)}
        sink = 1 + n + len(agents)
        edges: list[tuple[int, int, int, int]] = []
        for i, cid in enumerate(call_ids):
            edges.append((0, 1 + i, 1, 0))
            for agent in self.adjacency[cid]:
                if agent in agent_node:
                    edges.append(
                        (1 + i, agent_node[agent], 1, self.tier_cost(cid, agent, big))
                    )
        for a in agents:
            edges.append((agent_node[a], sink, 1, 0))
        return min_cost_flow(sink + 1, 0, sink, edges, n)


def plan(snapshot: Snapshot) -> PlanResult:
    """对输入快照规划整批来电的分配方案。"""
    ws = _Workspace(snapshot)
    all_ids = [c.call_id for c in ws.calls]
    if not all_ids:
        return PlanResult(assignments={}, waiting=())

    # 1. 接通总数最多
    max_count = max_matching_size(all_ids, ws.adjacency)

    # 2. 按优先级逐通确定接通名单：能接通就强制接通
    connected: list[int] = []
    for cid in all_ids:
        if len(connected) == max_count:
            break
        if max_matching_size(connected + [cid], ws.adjacency) == len(connected) + 1:
            connected.append(cid)

    # 3. 升级层级最少：先三级数最少，再二级数最少（big 大于任何可能的二级总数）
    big = max_count + 1
    initial = ws.min_upgrade_cost(connected, set(), big)
    assert initial is not None  # 接通名单已验证可行，必有解
    _, best_cost = initial
    best_t3, best_t2 = divmod(best_cost, big)

    # 4. 按优先级依次为每通已接通来电确定最小可行坐席编号
    assignments: dict[int, int] = {}
    used_t3 = 0
    used_t2 = 0
    for index, cid in enumerate(connected):
        remaining = connected[index + 1 :]
        for agent in ws.adjacency[cid]:
            if agent in assignments.values():
                continue
            tier = ws.tiers[cid][agent]
            add_t3 = 1 if tier == 3 else 0
            add_t2 = 1 if tier == 2 else 0
            if used_t3 + add_t3 > best_t3 or used_t2 + add_t2 > best_t2:
                continue
            excluded = set(assignments.values()) | {agent}
            result = ws.min_upgrade_cost(remaining, excluded, big)
            if result is None:
                continue
            _, cost = result
            if cost == big * (best_t3 - used_t3 - add_t3) + (best_t2 - used_t2 - add_t2):
                assignments[cid] = agent
                used_t3 += add_t3
                used_t2 += add_t2
                break

    waiting = tuple(sorted(set(all_ids) - set(connected)))
    return PlanResult(assignments=assignments, waiting=waiting)
