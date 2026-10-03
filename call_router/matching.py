"""二分图匹配与最小费用流工具（内部实现）。"""

from __future__ import annotations

import heapq


def max_matching_size(
    left_nodes: list[int],
    adjacency: dict[int, list[int]],
) -> int:
    """左侧节点到右侧节点的最大匹配大小。adjacency 的右侧节点为任意可哈希对象。"""
    match_right: dict[object, int] = {}

    def augment(left: int, seen: set[object]) -> bool:
        for right in adjacency.get(left, []):
            if right in seen:
                continue
            seen.add(right)
            if right not in match_right or augment(match_right[right], seen):
                match_right[right] = left
                return True
        return False

    size = 0
    for left in left_nodes:
        if augment(left, set()):
            size += 1
    return size


def min_cost_flow(
    num_nodes: int,
    source: int,
    sink: int,
    edges: list[tuple[int, int, int, int]],
    required_flow: int,
) -> tuple[int, int] | None:
    """最小费用最大流。edges 为 (起点, 终点, 容量, 单位费用)。

    返回 (流量, 费用)；若无法达到 required_flow 返回 None。
    """
    graph: list[list[list[int]]] = [[] for _ in range(num_nodes)]
    # 每条边存 [终点, 剩余容量, 单位费用, 反向边下标]
    for u, v, cap, cost in edges:
        graph[u].append([v, cap, cost, len(graph[v])])
        graph[v].append([u, 0, -cost, len(graph[u]) - 1])

    total_flow = 0
    total_cost = 0
    potential = [0] * num_nodes
    inf = float("inf")

    while total_flow < required_flow:
        dist = [inf] * num_nodes
        prev_node = [-1] * num_nodes
        prev_edge = [-1] * num_nodes
        dist[source] = 0
        heap = [(0, source)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            for i, edge in enumerate(graph[u]):
                v, cap, cost, _ = edge
                if cap <= 0:
                    continue
                nd = d + cost + potential[u] - potential[v]
                if nd < dist[v]:
                    dist[v] = nd
                    prev_node[v] = u
                    prev_edge[v] = i
                    heapq.heappush(heap, (nd, v))
        if dist[sink] == inf:
            return None
        for u in range(num_nodes):
            if dist[u] < inf:
                potential[u] += dist[u]
        # 沿增广路推送（本库中容量均为 1，推送量取路径最小容量）
        push = required_flow - total_flow
        v = sink
        while v != source:
            u = prev_node[v]
            push = min(push, graph[u][prev_edge[v]][1])
            v = u
        v = sink
        while v != source:
            u = prev_node[v]
            edge = graph[u][prev_edge[v]]
            edge[1] -= push
            graph[v][edge[3]][1] += push
            total_cost += push * edge[2]
            v = u
        total_flow += push

    return total_flow, total_cost
