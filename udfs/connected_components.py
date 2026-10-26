"""Exasol Python SET-EMITS UDF for resolving connected components into Golden Customer IDs."""

from typing import Dict, List


class DisjointSet:
    """Disjoint Set Union (DSU) data structure with path compression."""

    def __init__(self) -> None:
        self.parent: Dict[str, str] = {}

    def find(self, item: str) -> str:
        if item not in self.parent:
            self.parent[item] = item
            return item
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, item1: str, item2: str) -> None:
        root1 = self.find(item1)
        root2 = self.find(item2)
        if root1 != root2:
            # Deterministically anchor on lexically smaller root
            if root1 < root2:
                self.parent[root2] = root1
            else:
                self.parent[root1] = root2


def resolve_clusters(edges: List[tuple[str, str]]) -> Dict[str, str]:
    """Resolve graph of pairwise edges into canonical golden customer mapping."""
    dsu = DisjointSet()
    nodes = set()
    for u, v in edges:
        nodes.add(u)
        nodes.add(v)
        dsu.union(u, v)

    mapping = {}
    for node in nodes:
        root = dsu.find(node)
        mapping[node] = f"GOLD_{root}"
    return mapping


def run(ctx):
    """Exasol SET-EMITS UDF entrypoint."""
    edges = []
    while True:
        if ctx.id1 and ctx.id2:
            edges.append((ctx.id1, ctx.id2))
        if not ctx.next():
            break

    mapping = resolve_clusters(edges)
    # Count cluster sizes
    counts: Dict[str, int] = {}
    for gid in mapping.values():
        counts[gid] = counts.get(gid, 0) + 1

    for tid, gid in mapping.items():
        ctx.emit(tid, gid, counts[gid])
