"""Tests for construction-specific extraction: entity types, predecessor edges, temporal queries."""
from __future__ import annotations

import datetime
import json
from unittest.mock import MagicMock, patch

import networkx as nx
import pytest

from graphify_construct.build import build_from_json
from graphify_construct.validate import VALID_FILE_TYPES, validate_extraction
from graphify_construct.temporal import tasks_due_before


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONSTRUCTION_EXTRACTION = {
    "nodes": [
        {
            "id": "rfi042_document",
            "label": "RFI-042 Parapet Flashing",
            "file_type": "document",
            "source_file": "rfi-042.md",
            "due_date": "2026-06-15",
        },
        {
            "id": "schedule_install_roofing",
            "label": "Install Roofing",
            "file_type": "task",
            "source_file": "schedule.md",
            "start_date": "2026-05-18",
            "due_date": "2026-05-25",
            "duration_days": 7,
            "predecessors": ["schedule_frame_walls"],
        },
        {
            "id": "schedule_frame_walls",
            "label": "Frame Walls",
            "file_type": "task",
            "source_file": "schedule.md",
            "start_date": "2026-05-07",
            "due_date": "2026-05-17",
            "duration_days": 10,
            "predecessors": ["schedule_foundation"],
        },
        {
            "id": "schedule_foundation",
            "label": "Pour Foundation",
            "file_type": "task",
            "source_file": "schedule.md",
            "start_date": "2026-05-01",
            "due_date": "2026-05-06",
            "duration_days": 5,
            "predecessors": [],
        },
        {
            "id": "contract_abc_roofing",
            "label": "ABC Roofing Co.",
            "file_type": "institution",
            "source_file": "contract-abc-roofing.md",
        },
        {
            "id": "contract_john_smith",
            "label": "John Smith",
            "file_type": "person",
            "source_file": "contract-abc-roofing.md",
        },
        {
            "id": "schedule_co",
            "label": "Certificate of Occupancy",
            "file_type": "deadline",
            "source_file": "schedule.md",
            "due_date": "2026-07-15",
        },
    ],
    "edges": [
        {
            "source": "contract_john_smith",
            "target": "contract_abc_roofing",
            "relation": "member_of",
            "confidence": "EXTRACTED",
            "source_file": "contract-abc-roofing.md",
        },
    ],
    "hyperedges": [],
    "input_tokens": 100,
    "output_tokens": 200,
}


# ---------------------------------------------------------------------------
# Tests: entity types
# ---------------------------------------------------------------------------

class TestEntityTypes:
    def test_all_valid_file_types(self):
        """All file_type values in the fixture must be in VALID_FILE_TYPES."""
        for node in CONSTRUCTION_EXTRACTION["nodes"]:
            assert node["file_type"] in VALID_FILE_TYPES, (
                f"Node {node['id']!r} has invalid file_type {node['file_type']!r}"
            )

    def test_valid_file_types_set(self):
        expected = {"document", "task", "person", "institution", "building",
                    "location", "equipment", "deadline", "permit"}
        assert VALID_FILE_TYPES == expected

    def test_validate_extraction_passes(self):
        errors = validate_extraction(CONSTRUCTION_EXTRACTION)
        assert errors == [], f"Unexpected validation errors: {errors}"


# ---------------------------------------------------------------------------
# Tests: predecessor materialization
# ---------------------------------------------------------------------------

class TestPredecessorMaterialization:
    def test_precedes_edges_materialized(self):
        G = build_from_json(CONSTRUCTION_EXTRACTION)
        # foundation → framing → roofing should all be present as precedes edges
        assert G.has_edge("schedule_foundation", "schedule_frame_walls"), \
            "foundation → framing precedes edge missing"
        assert G.has_edge("schedule_frame_walls", "schedule_install_roofing"), \
            "framing → roofing precedes edge missing"

    def test_precedes_edge_has_correct_relation(self):
        G = build_from_json(CONSTRUCTION_EXTRACTION)
        edge_data = G.edges["schedule_foundation", "schedule_frame_walls"]
        assert edge_data.get("relation") == "precedes"
        assert edge_data.get("confidence") == "EXTRACTED"


# ---------------------------------------------------------------------------
# Tests: tasks_due_before
# ---------------------------------------------------------------------------

class TestTasksDueBefore:
    def test_tasks_due_before_july(self):
        G = build_from_json(CONSTRUCTION_EXTRACTION)
        due = tasks_due_before(G, datetime.date(2026, 7, 1))
        ids = {r["id"] for r in due}
        # All task nodes with due_date before 2026-07-01
        assert "schedule_foundation" in ids
        assert "schedule_frame_walls" in ids
        assert "schedule_install_roofing" in ids
        # Deadline node should also appear (it's a deadline type)
        # CO deadline is 2026-07-15 which is after 2026-07-01, so should NOT appear
        assert "schedule_co" not in ids

    def test_rfi_document_not_returned(self):
        """Documents are not tasks — tasks_due_before should not include them."""
        G = build_from_json(CONSTRUCTION_EXTRACTION)
        due = tasks_due_before(G, datetime.date(2026, 12, 31))
        ids = {r["id"] for r in due}
        assert "rfi042_document" not in ids
