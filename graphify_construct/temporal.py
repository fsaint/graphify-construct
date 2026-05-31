from __future__ import annotations

import datetime
import sys
from typing import Union

import networkx as nx

DateLike = Union[datetime.date, None]

_DATE_FIELDS = ("start_date", "due_date", "completed_at")
_DEPENDENCY_RELATIONS = frozenset({"precedes", "depends_on", "blocks"})
_TASK_TYPES = frozenset({"task", "deadline"})


def parse_dates(G: nx.Graph) -> None:
    """Attach datetime.date objects to node attrs in-place from ISO string fields."""
    for _, data in G.nodes(data=True):
        for field in _DATE_FIELDS:
            raw = data.get(field)
            if raw is None:
                continue
            if isinstance(raw, datetime.date):
                continue
            try:
                data[field] = datetime.date.fromisoformat(str(raw))
            except (ValueError, TypeError):
                data[field] = None


def _is_task_node(data: dict) -> bool:
    return data.get("file_type") in _TASK_TYPES


def build_dependency_dag(G: nx.Graph) -> nx.DiGraph:
    """DiGraph of task/deadline nodes connected by dependency edges. Warns on cycles."""
    dag: nx.DiGraph = nx.DiGraph()
    for nid, data in G.nodes(data=True):
        if _is_task_node(data):
            dag.add_node(nid, **data)

    for u, v, data in G.edges(data=True):
        if data.get("relation") in _DEPENDENCY_RELATIONS:
            if u in dag and v in dag:
                dag.add_edge(u, v, **data)

    if not nx.is_directed_acyclic_graph(dag):
        try:
            cycle = nx.find_cycle(dag)
            # Drop the lowest-confidence edge in the cycle
            worst = min(
                cycle,
                key=lambda e: dag.edges[e[0], e[1]].get("confidence_score", 1.0),
            )
            print(
                f"[graphify-construct] Warning: dependency cycle detected; "
                f"dropping edge {worst[0]!r} → {worst[1]!r}.",
                file=sys.stderr,
            )
            dag.remove_edge(worst[0], worst[1])
        except nx.NetworkXNoCycle:
            pass

    return dag


def critical_path(dag: nx.DiGraph) -> tuple[list[str], int]:
    """Longest-duration path using duration_days. Returns (ordered node IDs, total days)."""
    if not dag.nodes:
        return [], 0

    if not nx.is_directed_acyclic_graph(dag):
        return [], 0

    def _dur(nid: str) -> int:
        d = dag.nodes[nid].get("duration_days")
        try:
            return int(d) if d is not None else 1
        except (ValueError, TypeError):
            return 1

    # dag_longest_path uses *edge* weights; set each edge weight to the
    # destination node's duration so path selection is duration-driven,
    # not edge-count-driven. The source node's duration is added separately
    # as the starting cost after the path is found.
    weighted: nx.DiGraph = dag.copy()
    for u, v in weighted.edges():
        weighted.edges[u, v]["_dur"] = _dur(v)

    path = nx.dag_longest_path(weighted, weight="_dur")
    total = sum(_dur(n) for n in path)
    return path, total


def tasks_due_before(G: nx.Graph, when: datetime.date) -> list[dict]:
    """Task nodes with due_date <= when and completed_at is None."""
    parse_dates(G)
    result = []
    for nid, data in G.nodes(data=True):
        if not _is_task_node(data):
            continue
        due = data.get("due_date")
        if not isinstance(due, datetime.date):
            continue
        if due <= when and data.get("completed_at") is None:
            result.append({
                "id": nid,
                "label": data.get("label", nid),
                "due_date": due.isoformat(),
                "responsible_party": data.get("responsible_party"),
                "source_file": data.get("source_file"),
            })
    result.sort(key=lambda d: d["due_date"])
    return result


def dependency_chain(
    G: nx.Graph,
    task_id: str,
    direction: str = "both",
) -> list[str]:
    """Upstream and/or downstream tasks from a given task.

    direction: "up" (predecessors), "down" (successors), "both".
    """
    dag = build_dependency_dag(G)
    if task_id not in dag:
        return []

    result_set: set[str] = set()

    if direction in ("up", "both"):
        result_set.update(nx.ancestors(dag, task_id))

    if direction in ("down", "both"):
        result_set.update(nx.descendants(dag, task_id))

    # Return in topological order, filtered to result_set
    try:
        topo = list(nx.topological_sort(dag))
    except nx.NetworkXUnfeasible:
        return sorted(result_set)

    return [n for n in topo if n in result_set]


def slack(dag: nx.DiGraph) -> dict[str, int]:
    """Per-task float = latest_start - earliest_start.

    Uses duration_days for each node (defaults to 1 if missing).
    Returns a dict mapping node_id → slack_days.
    """
    if not dag.nodes or not nx.is_directed_acyclic_graph(dag):
        return {}

    def dur(nid: str) -> int:
        d = dag.nodes[nid].get("duration_days")
        try:
            return int(d) if d is not None else 1
        except (ValueError, TypeError):
            return 1

    # Forward pass: earliest_start[n]
    earliest: dict[str, int] = {}
    for nid in nx.topological_sort(dag):
        preds = list(dag.predecessors(nid))
        if not preds:
            earliest[nid] = 0
        else:
            earliest[nid] = max(earliest[p] + dur(p) for p in preds)

    # Backward pass: latest_start[n]
    project_end = max(earliest[n] + dur(n) for n in dag.nodes)
    latest: dict[str, int] = {}
    for nid in reversed(list(nx.topological_sort(dag))):
        succs = list(dag.successors(nid))
        if not succs:
            latest[nid] = project_end - dur(nid)
        else:
            latest[nid] = min(latest[s] - dur(nid) for s in succs)

    return {nid: latest[nid] - earliest[nid] for nid in dag.nodes}
