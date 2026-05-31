# graphify-construct skill

## Purpose
Turn construction project documents (PDFs, .docx, .xlsx, emails, schedules, photos) into a queryable knowledge graph of Documents, Tasks, People, Institutions, Buildings, Deadlines, Equipment, Locations, and Permits.

## Trigger
Use this skill when the user types `/graphify-construct` or asks to extract a knowledge graph from construction project documents.

## Entity types
| Type | Examples |
|------|---------|
| document | RFI, submittal, spec, contract, drawing, email, report |
| task | "pour foundation", "install roofing", "MEP rough-in" |
| person | Project manager, architect, inspector |
| institution | Contractor, subcontractor, agency, authority |
| building | Structure, facility, unit |
| location | Site, zone, room, floor, address |
| equipment | Machinery, material, tool, system |
| deadline | Date-anchored milestone |
| permit | Permit, approval, inspection result, certificate |

## Relation vocabulary
`responsible_for`, `depends_on`, `precedes`, `located_at`, `approves`, `supplies`, `inspected_by`, `references`, `cites`, `requires`, `blocks`, `due_before`, `owned_by`, `member_of`, `assigned_to`

## Extraction guidance
<!-- CANONICAL SOURCE: graphify_construct/llm.py:_EXTRACTION_SYSTEM — keep in sync -->
- Node ID format: lowercase [a-z0-9_] only, {stem}_{entity}
- Temporal fields: populate start_date, due_date, completed_at (ISO-8601) whenever a date appears
- Predecessors: fill predecessors[] when source implies ordering ("after foundation cures")
- Confidence: EXTRACTED (explicit), INFERRED (reasonable), AMBIGUOUS (uncertain — flag, don't omit)
- Prefer the most specific named entity
- Use AMBIGUOUS over dropping uncertain entities

## Output
- `graphify-out/graph.json` — knowledge graph
- `graphify-out/graph.html` — interactive visualization (tasks blue, deadlines red, persons green)
- `graphify-out/gantt.html` — Gantt chart with critical path (`graphify-construct export gantt`)
