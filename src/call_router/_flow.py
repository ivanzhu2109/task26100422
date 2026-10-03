"""Internal flow algorithms over a call-to-agent bipartite graph.

Costs are arbitrary-precision Python ints, so the planner can encode several
lexicographic objectives into a single edge weight.
"""

from __future__ import annotations

import heapq
from collections import deque

_INF = None  # distances use ``None`` for "unreachable" to stay int-friendly


def _build_residual(num_nodes, edges):
    """Build a residual network; returns (graph, origin_index_per_arc)."""
    graph = [[] for _ in range(num_nodes)]
    for index, (u, v, cap, cost) in enumerate(edges):
        graph[u].append([v, cap, cost, len(graph[v]), index])
        graph[v].append([u, 0, -cost, len(graph[u]) - 1, -1])
    return graph


def max_flow_value(num_nodes: int, edges: list[tuple[int, int, int, int]],
                   source: int, sink: int) -> int:
    """Plain Edmonds-Karp max flow; costs are ignored."""
    graph = _build_residual(num_nodes, edges)
    total = 0
    while True:
        prev = [None] * num_nodes  # node -> (arc_index, from_node)
        prev[source] = (-1, -1)
        queue = deque([source])
        while queue and prev[sink] is None:
            u = queue.popleft()
            for arc_index, arc in enumerate(graph[u]):
                if arc[1] > 0 and prev[arc[0]] is None:
                    prev[arc[0]] = (arc_index, u)
                    queue.append(arc[0])
        if prev[sink] is None:
            return total
        bottleneck = None
        node = sink
        while node != source:
            arc_index, parent = prev[node]
            cap = graph[parent][arc_index][1]
            bottleneck = cap if bottleneck is None else min(bottleneck, cap)
            node = parent
        node = sink
        while node != source:
            arc_index, parent = prev[node]
            arc = graph[parent][arc_index]
            arc[1] -= bottleneck
            graph[node][arc[3]][1] += bottleneck
            node = parent
        total += bottleneck


def min_cost_flow(num_nodes: int, edges: list[tuple[int, int, int, int]],
                  source: int, sink: int, flow_value: int) -> list[int]:
    """Min-cost flow of exactly ``flow_value`` units.

    Successive shortest augmenting paths with Johnson potentials; the initial
    potentials come from one Bellman-Ford pass so negative edge costs are fine.

    Returns:
        ``edge_flows`` where ``edge_flows[i]`` is the flow through ``edges[i]``.
    """
    graph = _build_residual(num_nodes, edges)

    # Initial potentials: shortest distances from source (Bellman-Ford/SPFA).
    potential = [None] * num_nodes
    potential[source] = 0
    in_queue = [False] * num_nodes
    in_queue[source] = True
    queue = deque([source])
    while queue:
        u = queue.popleft()
        in_queue[u] = False
        for arc in graph[u]:
            if arc[1] > 0:
                candidate = potential[u] + arc[2]
                if potential[arc[0]] is None or candidate < potential[arc[0]]:
                    potential[arc[0]] = candidate
                    if not in_queue[arc[0]]:
                        in_queue[arc[0]] = True
                        queue.append(arc[0])
    potential = [p if p is not None else 0 for p in potential]

    for _ in range(flow_value):
        dist = [None] * num_nodes
        dist[source] = 0
        prev = [None] * num_nodes
        heap = [(0, source)]
        while heap:
            d, u = heapq.heappop(heap)
            if dist[u] is not None and d > dist[u]:
                continue
            for arc_index, arc in enumerate(graph[u]):
                if arc[1] > 0:
                    reduced = arc[2] + potential[u] - potential[arc[0]]
                    candidate = d + reduced
                    if dist[arc[0]] is None or candidate < dist[arc[0]]:
                        dist[arc[0]] = candidate
                        prev[arc[0]] = (arc_index, u)
                        heapq.heappush(heap, (candidate, arc[0]))
        if dist[sink] is None:
            raise ValueError("required flow is not attainable")
        for node in range(num_nodes):
            if dist[node] is not None:
                potential[node] += dist[node]
        node = sink
        while node != source:
            arc_index, parent = prev[node]
            arc = graph[parent][arc_index]
            arc[1] -= 1
            graph[node][arc[3]][1] += 1
            node = parent

    edge_flows = [0] * len(edges)
    for u in range(num_nodes):
        for arc in graph[u]:
            if arc[4] >= 0:
                edge_flows[arc[4]] = edges[arc[4]][2] - arc[1]
    return edge_flows
