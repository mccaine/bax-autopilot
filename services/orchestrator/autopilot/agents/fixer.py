"""Fixer agent: read the failing build/test/compose report and patch code.

Increments ``fix_iters``; the graph's conditional edge stops looping once the
configured cap is hit (then the run is marked ``blocked`` with the report).
"""

from __future__ import annotations

from autopilot.agents.base import (
    call_llm,
    journal,
    load_prompt,
    parse_json,
    workspace_for,
)

SYSTEM = load_prompt("fixer") or (
    "You are a debugging expert. You are given failing build/test output and the "
    "current file tree of a Next.js + Node.js + PostgreSQL monorepo. Diagnose the "
    "root cause and emit corrected file contents. Respond with ONLY a JSON object "
    "mapping repo-relative paths to full corrected contents."
)

USER_TMPL = """Failure report:
{report}

Current files:
{tree}

Return JSON: {{ "path/to/file": "<full corrected contents>", ... }}
Only include files you are changing. Fix the root cause, not the symptom."""


def fix_node(state: dict) -> dict:
    ws = workspace_for(state)
    tree = "\n".join(ws.tree())[:6000]
    report = state.get("test_report", "") or state.get("review_notes", "")

    raw = call_llm("coder", SYSTEM, USER_TMPL.format(report=report[-6000:], tree=tree))
    files = parse_json(raw, default={})
    written = 0
    if isinstance(files, dict):
        for path, content in files.items():
            if isinstance(path, str) and isinstance(content, str):
                try:
                    ws.write(path, content)
                    written += 1
                except Exception:
                    continue

    iters = state.get("fix_iters", 0) + 1
    return {
        "fix_iters": iters,
        "phase": "test",
        "steps": state.get("steps", 0) + 1,
        **journal(f"fix #{iters}: patched {written} files"),
    }
