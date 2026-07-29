"""Coder agent: implement each task by writing files into the workspace.

Fans out over the architect's task list. For each task the coder model is given
the current file tree + the task and returns a JSON map of ``path -> contents``
that we write beneath the workspace. Real logic replaces scaffold stubs.
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


def implement_node(state: dict) -> dict:
    ws = workspace_for(state)
    tasks = state.get("tasks", [])
    total = 0
    done_lines = []
    for task in tasks:
        if task.get("done"):
            continue
        n = _implement_one(state, task, ws)
        task["done"] = True
        total += n
        done_lines.append(f"{task.get('id')}:{task.get('service')} (+{n} files)")

    return {
        "tasks": tasks,
        "phase": "test",
        "steps": state.get("steps", 0) + 1,
        **journal(f"implement: {total} files across {len(done_lines)} tasks — {', '.join(done_lines)}"),
    }
