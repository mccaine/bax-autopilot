"""Coder agent: implement tasks by writing files into the workspace.

Runs as a **fan-out worker**: the graph dispatches one ``coder_worker`` per task
(LangGraph ``Send``), so tasks are implemented in parallel (bounded by
``max_parallel_coders``). Each worker returns only reducer-keyed fields so the
concurrent results merge cleanly.
"""

from __future__ import annotations

from autopilot.agents.base import (
    call_llm,
    journal,
    load_prompt,
    parse_json,
    workspace_for,
)

SYSTEM = load_prompt("coder") or (
    "You are an expert full-stack engineer working in a Next.js + Node.js (Express) + "
    "PostgreSQL monorepo. Implement the requested task by emitting complete file "
    "contents. Respond with ONLY a JSON object mapping repo-relative file paths to "
    "their full contents. Do not include explanations."
)

USER_TMPL = """App: {app_name}
Service: {service}
Task: {title}
Detail: {detail}

Existing files (relative paths):
{tree}

Return JSON: {{ "path/to/file.ts": "<full file contents>", ... }}
Write only files needed for THIS task. Keep them consistent with the existing tree."""


def _implement_one(state: dict, task: dict, ws) -> int:
    """Implement a single task, writing files. Returns files written. Reusable by
    both the fan-out worker and any sequential caller."""
    tree = "\n".join(ws.tree())[:6000]
    raw = call_llm(
        "coder",
        SYSTEM,
        USER_TMPL.format(
            app_name=state.get("spec", {}).get("name", "app"),
            service=task.get("service", "?"),
            title=task.get("title", ""),
            detail=task.get("detail", ""),
            tree=tree,
        ),
    )
    files = parse_json(raw, default={})
    written = 0
    if isinstance(files, dict):
        for path, content in files.items():
            if isinstance(path, str) and isinstance(content, str):
                try:
                    ws.write(path, content)
                    written += 1
                except Exception:  # path escape etc. — skip, keep going
                    continue
    return written


def coder_worker_node(state: dict) -> dict:
    """Fan-out worker: implement ``state['current_task']`` (a Send payload).

    Returns only reducer-merged keys (``implemented``, ``journal``) so parallel
    workers don't clobber each other's state.
    """
    task = state["current_task"]
    ws = workspace_for(state)
    n = _implement_one(state, task, ws)
    label = f"{task.get('id', '?')}:{task.get('service', '?')} (+{n} files)"
    return {"implemented": [label], **journal(f"code: {label}")}
