"""Spec agent: raw intent → structured product spec."""

from __future__ import annotations

from autopilot.agents.base import call_llm, journal, load_prompt, parse_json

SYSTEM = load_prompt("spec") or (
    "You are a senior product engineer. Turn a one-line app intent into a precise, "
    "buildable spec for a containerized web app (Next.js frontend, Node.js services, "
    "PostgreSQL). Respond with ONLY a JSON object, no prose."
)

USER_TMPL = """Intent: {intent}

Return JSON with exactly these keys:
{{
  "name": "kebab-case-app-name",
  "summary": "one sentence",
  "features": ["..."],
  "entities": [{{"name": "Task", "fields": [{{"name":"title","type":"string"}}]}}],
  "pages": ["/", "/login"],
  "acceptance_criteria": ["..."]
}}"""


def spec_node(state: dict) -> dict:
    intent = state["intent"]
    raw = call_llm("planner", SYSTEM, USER_TMPL.format(intent=intent))
    spec = parse_json(raw, default=None)
    if not isinstance(spec, dict) or "name" not in spec:
        # Fallback so the pipeline still proceeds with a minimal, valid spec.
        spec = {
            "name": "generated-app",
            "summary": intent,
            "features": [intent],
            "entities": [],
            "pages": ["/"],
            "acceptance_criteria": ["app builds and starts", "home page responds 200"],
        }
    return {
        "spec": spec,
        "phase": "architect",
        "steps": state.get("steps", 0) + 1,
        **journal(f"spec: {spec.get('name')} — {len(spec.get('features', []))} features"),
    }
