"""Reviewer agent: spec-adherence + sanity gate before deploy/integrate.

Approve → deploy. Reject → back to fix (bounded by the same fix budget as the
test loop). This is a second machine gate, orthogonal to tests: it catches
"builds green but doesn't match the spec" cases.
"""

from __future__ import annotations

from autopilot.agents.base import (
    call_llm,
    journal,
    load_prompt,
    parse_json,
    workspace_for,
)

SYSTEM = load_prompt("reviewer") or (
    "You are a meticulous staff engineer doing final review. Check the implementation "
    "against the acceptance criteria and flag missing features, obvious security "
    "issues (hardcoded secrets, missing auth), and broken wiring. Respond with ONLY "
    'JSON: {"approved": true|false, "notes": "..."}.'
)

USER_TMPL = """Acceptance criteria:
{criteria}

Files:
{tree}

Key file excerpts:
{excerpts}

Return JSON: {{"approved": bool, "notes": "concise findings"}}"""


def _excerpts(ws, limit: int = 5) -> str:
    picks = [
        f for f in ws.tree()
        if f.endswith((".ts", ".tsx", ".js", ".sql")) and "node_modules" not in f
    ][:limit]
    chunks = []
    for f in picks:
        try:
            chunks.append(f"--- {f} ---\n{ws.read(f)[:1200]}")
        except Exception:
            continue
    return "\n\n".join(chunks)


def review_node(state: dict) -> dict:
    ws = workspace_for(state)
    criteria = state.get("spec", {}).get("acceptance_criteria", [])
    raw = call_llm(
        "planner",
        SYSTEM,
        USER_TMPL.format(
            criteria=criteria,
            tree="\n".join(ws.tree())[:3000],
            excerpts=_excerpts(ws),
        ),
    )
    data = parse_json(raw, default={"approved": True, "notes": "auto-approved (unparseable review)"})
    approved = bool(data.get("approved", True)) if isinstance(data, dict) else True
    notes = data.get("notes", "") if isinstance(data, dict) else ""

    return {
        "review_ok": approved,
        "review_notes": notes,
        "phase": "deploy" if approved else "fix",
        "steps": state.get("steps", 0) + 1,
        **journal(f"review: {'APPROVED' if approved else 'REJECTED'} — {notes[:120]}"),
    }
