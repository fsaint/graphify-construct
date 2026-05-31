"""Tests for graphify_construct.temporal — critical path, due-date filtering, and slack."""
from __future__ import annotations

import datetime
import networkx as nx
import pytest

from graphify_construct.temporal import (
    build_dependency_dag,
    critical_path,
    dependency_chain,
    parse_dates,
    slack,
    tasks_due_before,
)


def _make_schedule_graph() -> nx.DiGraph:
    """Linear schedule: foundation → framing → roofing."""
    G = nx.DiGraph()
    G.add_node("foundation", file_type="task", label="Pour Foundation",
               duration_days=5, start_date="2026-05-01", due_date="2026-06-10")
    G.add_node("framing", file_type="task", label="Frame Walls",
               duration_days=10, start_date="2026-05-07", due_date="2026-06-20")
    G.add_node("roofing", file_type="task", label="Install Roofing",
               duration_days=7, start_date="2026-05-18", due_date="2026-07-01")
    G.add_edge("foundation", "framing",
               relation="precedes", confidence="EXTRACTED", confidence_score=1.0)
    G.add_edge("framing", "roofing",
               relation="precedes", confidence="EXTRACTED", confidence_score=1.0)
    return G


class TestCriticalPath:
    def test_linear_chain(self):
        G = _make_schedule_graph()
        dag = build_dependency_dag(G)
        path, total = critical_path(dag)
        assert path == ["foundation", "framing", "roofing"]
        assert total == 22  # 5 + 10 + 7

    def test_empty_graph(self):
        path, total = critical_path(nx.DiGraph())
        assert path == []
        assert total == 0

    def test_single_node(self):
        G = nx.DiGraph()
        G.add_node("solo", file_type="task", duration_days=3)
        dag = build_dependency_dag(G)
        path, total = critical_path(dag)
        assert path == ["solo"]
        assert total == 3

    def test_parallel_tasks_picks_longest(self):
        G = nx.DiGraph()
        G.add_node("start", file_type="task", duration_days=2)
        G.add_node("short", file_type="task", duration_days=3)
        G.add_node("long", file_type="task", duration_days=8)
        G.add_node("end", file_type="task", duration_days=2)
        G.add_edge("start", "short", relation="precedes", confidence="EXTRACTED", confidence_score=1.0)
        G.add_edge("start", "long", relation="precedes", confidence="EXTRACTED", confidence_score=1.0)
        G.add_edge("short", "end", relation="precedes", confidence="EXTRACTED", confidence_score=1.0)
        G.add_edge("long", "end", relation="precedes", confidence="EXTRACTED", confidence_score=1.0)
        dag = build_dependency_dag(G)
        path, total = critical_path(dag)
        assert "long" in path
        assert "short" not in path
        assert total == 12  # 2 + 8 + 2


class TestTasksDueBefore:
    def test_returns_due_tasks(self):
        G = _make_schedule_graph()
        result = tasks_due_before(G, datetime.date(2026, 6, 15))
        ids = [r["id"] for r in result]
        assert "foundation" in ids
        assert "framing" not in ids
        assert "roofing" not in ids

    def test_excludes_completed(self):
        G = nx.DiGraph()
        G.add_node("done", file_type="task", due_date="2026-06-01",
                   completed_at="2026-05-30")
        G.add_node("open", file_type="task", due_date="2026-06-01")
        result = tasks_due_before(G, datetime.date(2026, 6, 30))
        ids = [r["id"] for r in result]
        assert "done" not in ids
        assert "open" in ids

    def test_sorted_by_due_date(self):
        G = nx.DiGraph()
        G.add_node("b", file_type="task", due_date="2026-06-10")
        G.add_node("a", file_type="task", due_date="2026-06-01")
        result = tasks_due_before(G, datetime.date(2026, 6, 30))
        assert result[0]["id"] == "a"
        assert result[1]["id"] == "b"


class TestCycleDetection:
    def test_cycle_warns_not_crashes(self, capsys):
        G = nx.DiGraph()
        G.add_node("a", file_type="task")
        G.add_node("b", file_type="task")
        G.add_edge("a", "b", relation="precedes", confidence="EXTRACTED", confidence_score=1.0)
        G.add_edge("b", "a", relation="precedes", confidence="EXTRACTED", confidence_score=0.3)
        # Should not raise — cycle should be detected and one edge dropped
        dag = build_dependency_dag(G)
        assert nx.is_directed_acyclic_graph(dag)
        captured = capsys.readouterr()
        assert "cycle" in captured.err.lower()


class TestSlack:
    def test_critical_path_has_zero_slack(self):
        G = _make_schedule_graph()
        dag = build_dependency_dag(G)
        s = slack(dag)
        assert s["foundation"] == 0
        assert s["framing"] == 0
        assert s["roofing"] == 0

    def test_parallel_non_critical_has_slack(self):
        G = nx.DiGraph()
        G.add_node("start", file_type="task", duration_days=1)
        G.add_node("critical", file_type="task", duration_days=10)
        G.add_node("float_task", file_type="task", duration_days=2)
        G.add_node("end", file_type="task", duration_days=1)
        G.add_edge("start", "critical", relation="precedes", confidence="EXTRACTED", confidence_score=1.0)
        G.add_edge("start", "float_task", relation="precedes", confidence="EXTRACTED", confidence_score=1.0)
        G.add_edge("critical", "end", relation="precedes", confidence="EXTRACTED", confidence_score=1.0)
        G.add_edge("float_task", "end", relation="precedes", confidence="EXTRACTED", confidence_score=1.0)
        dag = build_dependency_dag(G)
        s = slack(dag)
        assert s["float_task"] == 8  # 10 - 2 = 8 days of float
        assert s["critical"] == 0
