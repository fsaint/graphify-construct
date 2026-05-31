# graphify-construct

Turn construction project documents into a queryable knowledge graph — PDFs, Word docs, Excel schedules, emails, and photos become a connected graph of Tasks, People, Buildings, Deadlines, Permits, and more.

```
graphify-construct extract ./project-docs --backend claude
```

That's it. You get three files:

```
graphify-out/
├── graph.html      open in any browser — tasks blue, deadlines red, persons green
├── graph.json      the full graph — query it anytime
└── GRAPH_REPORT.md highlights: key entities, dependencies, suggested questions
```

Add a Gantt chart with critical path highlighted in red:

```bash
graphify-construct export gantt
# → graphify-out/gantt.html
```

---

## Prerequisites

| Requirement | Minimum | Check | Install |
|---|---|---|---|
| Python | 3.10+ | `python --version` | [python.org](https://www.python.org/downloads/) |
| uv | any | `uv --version` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| An LLM API key | — | — | See [Backends](#backends) |

---

## Install

```bash
# From source (recommended for now):
git clone https://github.com/fsaint/graphify-construct
cd graphify-construct
uv tool install -e .

# Register the skill with Claude Code:
graphify-construct install
```

### Optional extras

| Extra | What it adds | Install |
|---|---|---|
| `pdf` | PDF extraction | `pip install "graphify-construct[pdf]"` |
| `office` | `.docx` and `.xlsx` | `pip install "graphify-construct[office]"` |
| `mcp` | MCP stdio server | `pip install "graphify-construct[mcp]"` |

---

## Extract a project

Point it at a folder of construction documents:

```bash
graphify-construct extract ./project-docs --backend claude
```

Supported file types:

| Type | Extensions |
|------|-----------|
| Docs / specs | `.md .txt .html .rst .yaml` |
| Word | `.docx` (requires `[office]`) |
| Excel | `.xlsx` (requires `[office]`) |
| PDFs | `.pdf` (requires `[pdf]`) |
| Images | `.png .jpg .webp` |

Binary CAD files (`.dwg`, `.rvt`, `.ifc`) are automatically skipped.

---

## Backends

| Backend | Flag | Key required |
|---|---|---|
| Claude (Anthropic) | `--backend claude` | `ANTHROPIC_API_KEY` |
| Claude Code CLI | `--backend claude-cli` | none — uses your Claude subscription |
| OpenAI | `--backend openai` | `OPENAI_API_KEY` |
| Gemini | `--backend gemini` | `GEMINI_API_KEY` |
| Ollama (local) | `--backend ollama` | none |

---

## Entity types

graphify-construct extracts 9 construction-specific entity types:

| Type | Examples |
|------|---------|
| `document` | RFI, submittal, spec, contract, drawing, email, report |
| `task` | "Pour Foundation", "Install Roofing", "MEP Rough-in" |
| `person` | Project manager, architect, inspector, superintendent |
| `institution` | Contractor, subcontractor, agency, authority having jurisdiction |
| `building` | Structure, facility, unit |
| `location` | Site, zone, room, floor, address |
| `equipment` | Machinery, material, tool, system |
| `deadline` | Date-anchored milestone (Certificate of Occupancy, permit expiry) |
| `permit` | Permit, approval, inspection result, certificate |

### Relation vocabulary

`responsible_for` · `depends_on` · `precedes` · `located_at` · `approves` · `supplies` · `inspected_by` · `references` · `cites` · `requires` · `blocks` · `due_before` · `owned_by` · `member_of` · `assigned_to`

---

## Query the graph

```bash
# Natural language queries
graphify-construct query "what tasks depend on the roofing submittal approval?"
graphify-construct query "who is responsible for MEP rough-in?"
graphify-construct query "what permits are still open?"

# Find shortest path between two entities
graphify-construct path "ABC Roofing Co." "Certificate of Occupancy"

# Explain a specific entity
graphify-construct explain "RFI-042"
```

---

## Gantt chart

```bash
graphify-construct export gantt
# → graphify-out/gantt.html

# Custom output path
graphify-construct export gantt --output docs/schedule.html
```

The Gantt chart:
- Shows all `task` and `deadline` nodes on a weekly timeline
- Highlights the **critical path** in red
- Side panel shows responsible party, source document, and predecessors on click
- Auto-calculates end dates from `duration_days` when no explicit date is set

---

## MCP server

Expose the graph as an MCP tool server for Claude Code or any MCP-compatible client:

```bash
python -m graphify_construct.serve graphify-out/graph.json
```

Available tools:

| Tool | Description |
|------|-------------|
| `query_graph` | Natural language BFS/DFS search |
| `get_node` | Full details for a node by label or ID |
| `get_neighbors` | Direct neighbors with edge details |
| `tasks_due_before` | Tasks with `due_date ≤ date` and not yet completed |
| `dependency_chain` | Upstream and/or downstream tasks from a given task |
| `responsible_for` | Tasks and docs linked to a person or institution |
| `critical_path` | Critical path through all tasks + total duration in days |
| `shortest_path` | Shortest path between two entities |
| `god_nodes` | Most-connected entities in the graph |
| `graph_stats` | Node count, edge count, confidence breakdown |

---

## Common commands

```bash
# Extract
graphify-construct extract ./docs --backend claude
graphify-construct extract ./docs --backend claude-cli   # no API key needed
graphify-construct extract ./docs --update               # re-extract changed files only
graphify-construct extract ./docs --mode deep            # richer extraction

# Export
graphify-construct export html                           # interactive graph
graphify-construct export gantt                          # Gantt + critical path
graphify-construct export gantt --output schedule.html
graphify-construct export obsidian                       # Obsidian vault

# Query
graphify-construct query "what blocks the CO?"
graphify-construct path "FoundationTask" "CertificateOfOccupancy"
graphify-construct explain "PermitNo123"

# Rebuild / cluster
graphify-construct extract ./docs --cluster-only         # rerun clustering only
graphify-construct extract ./docs --no-viz               # skip HTML

# Version
graphify-construct --version
```

---

## Temporal fields

When dates appear in source documents, graphify-construct extracts:

| Field | Description |
|---|---|
| `start_date` | Task start (ISO-8601) |
| `due_date` | Task or deadline due date (ISO-8601) |
| `completed_at` | Completion date, if known (ISO-8601) |
| `duration_days` | Duration in calendar days |
| `predecessors` | List of task IDs that must finish first |
| `responsible_party` | Person or institution node ID |

`predecessors[]` are automatically materialized as `precedes` edges in the graph so dependency queries and critical path work without any manual configuration.

---

## Development

```bash
git clone https://github.com/fsaint/graphify-construct
cd graphify-construct
uv sync --all-extras

# Run tests
uv run pytest tests/ -q

# Run only construction-specific tests
uv run pytest tests/test_temporal.py tests/test_gantt.py tests/test_construction_extract.py -v
```
