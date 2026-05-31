"""Tests for graphify_construct.gantt_html."""
from __future__ import annotations

import datetime
from pathlib import Path

import networkx as nx
import pytest

from graphify_construct.gantt_html import to_gantt_html


def _make_construction_graph() -> nx.DiGraph:
    G = nx.DiGraph()
    G.add_node("foundation", file_type="task", label="Pour Foundation",
               start_date="2026-05-01", due_date="2026-05-06", duration_days=5,
               source_file="schedule.md")
    G.add_node("framing", file_type="task", label="Frame Walls",
               start_date="2026-05-07", due_date="2026-05-17", duration_days=10,
               source_file="schedule.md", predecessors=["foundation"],
               responsible_party="eastgate_construction")
    G.add_node("roofing", file_type="task", label="Install Roofing",
               start_date="2026-05-18", due_date="2026-05-25", duration_days=7,
               source_file="submittal-roofing.md", predecessors=["framing"])
    G.add_node("co_deadline", file_type="deadline", label="Certificate of Occupancy",
               due_date="2026-07-15", source_file="schedule.md")
    G.add_edge("foundation", "framing",
               relation="precedes", confidence="EXTRACTED", confidence_score=1.0)
    G.add_edge("framing", "roofing",
               relation="precedes", confidence="EXTRACTED", confidence_score=1.0)
    return G


def test_gantt_html_created(tmp_path):
    G = _make_construction_graph()
    out = tmp_path / "gantt.html"
    to_gantt_html(G, out)
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert len(html) > 500


def test_four_task_bars(tmp_path):
    G = _make_construction_graph()
    out = tmp_path / "gantt.html"
    to_gantt_html(G, out)
    html = out.read_text(encoding="utf-8")
    assert "Pour Foundation" in html
    assert "Frame Walls" in html
    assert "Install Roofing" in html
    assert "Certificate of Occupancy" in html


def test_critical_path_class_applied(tmp_path):
    G = _make_construction_graph()
    out = tmp_path / "gantt.html"
    to_gantt_html(G, out)
    html = out.read_text(encoding="utf-8")
    assert "critical" in html


def test_frappe_gantt_cdn(tmp_path):
    G = _make_construction_graph()
    out = tmp_path / "gantt.html"
    to_gantt_html(G, out)
    html = out.read_text(encoding="utf-8")
    assert "frappe-gantt" in html


def test_empty_graph_produces_valid_html(tmp_path):
    G = nx.DiGraph()
    out = tmp_path / "empty_gantt.html"
    to_gantt_html(G, out)
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "No task" in html or len(html) > 0
