"""Fixer agent: read the failing build/test/compose report and patch code.

After patching, it does a **fast rebuild-only self-check** (`docker compose build`,
no up/healthcheck/tests) and may re-patch a couple of times against the build
error before handing back to the full test run — so trivial build breakages don't
burn an expensive up+test cycle each time.

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
from autopilot.config import get_settings
from autopilot.tools import compose

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


def _patch(state: dict, ws, report: str) -> int:
    tree = "\n".join(ws.tree())[:6000]
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
    return written


def _quick_build(app_dir):
    """Rebuild only (no up/test). Returns (ok, report) or (None, "") if the build
    can't be run here (e.g. no docker) so the caller skips the self-check."""
    try:
        r = compose.build(app_dir)
        return r.ok, r.summary()
    except Exception:
        return None, ""


def fix_node(state: dict) -> dict:
    settings = get_settings()
    ws = workspace_for(state)
    report = state.get("test_report", "") or state.get("review_notes", "")

    total = _patch(state, ws, report)
    notes = ["patch"]

    # Fast rebuild-only self-check + bounded re-patch against the build error.
    inner = 0
    while inner < settings.fix_inner_retries:
        ok, build_report = _quick_build(ws.root)
        if ok is None or ok:
            break  # build clean (or can't check here) → hand back to full test
        inner += 1
        total += _patch(state, ws, build_report)
        notes.append(f"rebuild#{inner}")

    iters = state.get("fix_iters", 0) + 1
    return {
        "fix_iters": iters,
        "phase": "test",
        "steps": state.get("steps", 0) + 1,
        **journal(f"fix #{iters}: patched {total} files ({', '.join(notes)})"),
    }
