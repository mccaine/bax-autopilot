"""Architect agent: spec → service decomposition + ordered task list."""

from __future__ import annotations

from autopilot.agents.base import call_llm, journal, load_prompt, parse_json

SYSTEM = load_prompt("architect") or (
    "You are a staff software architect. Given a product spec, design a containerized "
    "microservice monorepo: a Next.js frontend, one or more Node.js (Express) services, "
    "and a PostgreSQL database. Keep it minimal but complete. Respond with ONLY JSON."
)

USER_TMPL = """Spec:
{spec}

Return JSON:
{{
  "services": [
    {{"name": "frontend", "kind": "frontend", "description": "...", "port": 3000}},
    {{"name": "api", "kind": "service", "description": "...", "port": 4000}},
    {{"name": "db", "kind": "db", "description": "postgres", "port": 5432}}
  ],
  "tasks": [
    {{"id": "t1", "service": "api", "title": "Tasks CRUD endpoints", "detail": "..."}}
  ]
}}
Order tasks so that db schema and shared contracts come before dependents."""


def _fallback(spec: dict) -> tuple[list, list]:
    services = [
        {"name": "frontend", "kind": "frontend", "description": "Next.js UI", "port": 3000},
        {"name": "api", "kind": "service", "description": "Node.js REST API", "port": 4000},
        {"name": "db", "kind": "db", "description": "postgres", "port": 5432},
    ]
    tasks = [
        {"id": "t1", "service": "db", "title": "Schema + migrations", "detail": str(spec.get("entities", []))},
        {"id": "t2", "service": "api", "title": "REST endpoints", "detail": str(spec.get("features", []))},
        {"id": "t3", "service": "frontend", "title": "Pages + API calls", "detail": str(spec.get("pages", []))},
    ]
    return services, tasks


def architect_node(state: dict) -> dict:
    spec = state.get("spec", {})
    raw = call_llm("planner", SYSTEM, USER_TMPL.format(spec=spec))
    data = parse_json(raw, default={})
    services = data.get("services") if isinstance(data, dict) else None
    tasks = data.get("tasks") if isinstance(data, dict) else None
    if not services or not tasks:
        services, tasks = _fallback(spec)
    for t in tasks:
        t.setdefault("done", False)
    return {
        "services": services,
        "tasks": tasks,
        "phase": "scaffold",
        "steps": state.get("steps", 0) + 1,
        **journal(f"architect: {len(services)} services, {len(tasks)} tasks"),
    }
