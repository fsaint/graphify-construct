from __future__ import annotations

import json
import datetime
from pathlib import Path

import networkx as nx

from graphify_construct.security import sanitize_label
from graphify_construct.temporal import build_dependency_dag, critical_path, parse_dates


def _js_safe(obj: object) -> str:
    """Embed obj as a JSON literal safe for inline <script> use."""
    return json.dumps(obj, ensure_ascii=True, default=str).replace("</", "<\\/")


def _isodate(val: object) -> str | None:
    """Return ISO-8601 string from a date/str value, or None."""
    if val is None:
        return None
    if isinstance(val, datetime.date):
        return val.isoformat()
    try:
        datetime.date.fromisoformat(str(val))
        return str(val)
    except (ValueError, TypeError):
        return None


def to_gantt_html(G: nx.Graph, output_path: Path) -> None:
    """Render a self-contained Gantt HTML for all task/deadline nodes in G."""
    parse_dates(G)
    dag = build_dependency_dag(G)
    cp_nodes, _ = critical_path(dag)
    cp_set = set(cp_nodes)

    # Collect task/deadline nodes
    today = datetime.date.today()
    task_nodes = [
        (nid, data)
        for nid, data in G.nodes(data=True)
        if data.get("file_type") in {"task", "deadline"}
    ]

    if not task_nodes:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "<html><body><p>No task or deadline nodes found in graph.</p></body></html>",
            encoding="utf-8",
        )
        return

    task_node_ids = {nid for nid, _ in task_nodes}

    # Build Frappe Gantt task list
    gantt_tasks = []
    for nid, data in task_nodes:
        start = _isodate(data.get("start_date")) or today.isoformat()
        end = _isodate(data.get("due_date"))
        if end is None:
            dur = data.get("duration_days")
            try:
                dur_int = int(dur) if dur is not None else 1
            except (ValueError, TypeError):
                dur_int = 1
            end_date = datetime.date.fromisoformat(start) + datetime.timedelta(days=max(dur_int, 1))
            end = end_date.isoformat()

        preds = [
            str(p) for p in (data.get("predecessors") or [])
            if str(p) in task_node_ids
        ]
        # Also look at graph edges from the DAG
        if dag and nid in dag:
            for pred in dag.predecessors(nid):
                if pred not in preds:
                    preds.append(pred)

        gantt_tasks.append({
            "id": nid,
            "name": sanitize_label(data.get("label", nid)),
            "start": start,
            "end": end,
            "progress": 100 if data.get("completed_at") else 0,
            "dependencies": ",".join(preds),
            "custom_class": "critical" if nid in cp_set else "",
            "_responsible": data.get("responsible_party") or "",
            "_source_file": data.get("source_file") or "",
            "_predecessors": preds,
        })

    gantt_json = _js_safe([
        {k: v for k, v in t.items() if not k.startswith("_")}
        for t in gantt_tasks
    ])
    panel_data = _js_safe({t["id"]: {
        "responsible": t["_responsible"],
        "source_file": t["_source_file"],
        "predecessors": t["_predecessors"],
    } for t in gantt_tasks})

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Construction Schedule — Gantt</title>
<link rel="stylesheet"
      href="https://unpkg.com/frappe-gantt@0.6.1/dist/frappe-gantt.css"
      crossorigin="anonymous">
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; display: flex; height: 100vh; overflow: hidden; }}
  #gantt-wrap {{ flex: 1; overflow: auto; padding: 16px; }}
  #panel {{ width: 280px; border-left: 1px solid #e2e8f0; padding: 16px; overflow-y: auto; background: #f8fafc; }}
  #panel h3 {{ margin: 0 0 8px; font-size: 1rem; color: #1e293b; }}
  #panel p {{ margin: 4px 0; font-size: 0.85rem; color: #475569; word-break: break-all; }}
  #panel .label {{ font-weight: 600; color: #0f172a; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 10px; }}
  .bar-critical .bar {{ stroke: #ef4444 !important; stroke-width: 2px !important; }}
  .bar-critical .bar-label {{ fill: #7f1d1d !important; }}
  h1 {{ margin: 0 0 12px; font-size: 1.1rem; color: #1e293b; }}
</style>
</head>
<body>
<div id="gantt-wrap">
  <h1>Construction Schedule</h1>
  <div id="gantt"></div>
</div>
<div id="panel">
  <h3>Task Details</h3>
  <p style="color:#94a3b8">Click a task bar to see details.</p>
</div>
<script src="https://unpkg.com/frappe-gantt@0.6.1/dist/frappe-gantt.min.js"
        crossorigin="anonymous"></script>
<script>
const tasks = {gantt_json};
const panelData = {panel_data};

const gantt = new Gantt("#gantt", tasks, {{
  view_mode: "Week",
  date_format: "YYYY-MM-DD",
  on_click: function(task) {{
    const info = panelData[task.id] || {{}};
    const panel = document.getElementById("panel");
    panel.innerHTML = `
      <h3>${{task.name}}</h3>
      <div class="label">Responsible</div>
      <p>${{info.responsible || "\\u2014"}}</p>
      <div class="label">Source Document</div>
      <p>${{info.source_file || "\\u2014"}}</p>
      <div class="label">Predecessors</div>
      <p>${{(info.predecessors && info.predecessors.length) ? info.predecessors.join(", ") : "\\u2014"}}</p>
      <div class="label">Start</div>
      <p>${{task.start}}</p>
      <div class="label">End</div>
      <p>${{task.end}}</p>
      <div class="label">Progress</div>
      <p>${{task.progress}}%</p>
    `;
  }},
}});
</script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
