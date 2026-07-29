"""Scaffolder agent: materialize the microservice-monorepo template.

Deterministic (no LLM): copies the Jinja-rendered stack template into the
workspace, expanding per-service directories from the architect's service list.
This guarantees every run starts from a known-good, buildable skeleton; the
coder agent then fills in real logic.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from jinja2 import Environment, StrictUndefined

from autopilot.agents.base import journal
from autopilot.config import get_settings

_env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)


def _render(text: str, ctx: dict) -> str:
    try:
        return _env.from_string(text).render(**ctx)
    except Exception:
        # Non-templated binary-ish or oddly-braced files: copy verbatim.
        return text


def _render_tree(src: Path, dst: Path, ctx: dict) -> int:
    """Copy src→dst, rendering *.j2 files (dropping the suffix) and templating
    filenames containing __svc__ per service is handled by the caller."""
    count = 0
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if path.suffix == ".j2":
            target = target.with_suffix("")  # foo.ts.j2 -> foo.ts
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_render(path.read_text(encoding="utf-8"), ctx), encoding="utf-8")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        count += 1
    return count


def scaffold_node(state: dict) -> dict:
    settings = get_settings()
    spec = state.get("spec", {})
    services = state.get("services", [])
    workspace = Path(state["workspace"])
    workspace.mkdir(parents=True, exist_ok=True)

    template_root = Path(settings.stacks_dir) / "microservice-monorepo"
    ctx = {
        "app_name": spec.get("name", "generated-app"),
        "summary": spec.get("summary", state.get("intent", "")),
        "services": services,
        "node_services": [s for s in services if s.get("kind") == "service"],
        "frontends": [s for s in services if s.get("kind") == "frontend"],
        "region": settings.gcp_region,
        "project_id": settings.gcp_project_id or "REPLACE_ME",
    }

    files = 0
    if (template_root / "base").exists():
        files += _render_tree(template_root / "base", workspace, ctx)

    # Expand one directory per Node.js service from the service template.
    svc_template = template_root / "service"
    for svc in ctx["node_services"]:
        svc_ctx = {**ctx, "service": svc, "service_name": svc["name"], "port": svc.get("port", 4000)}
        dst = workspace / "services" / svc["name"]
        if svc_template.exists():
            files += _render_tree(svc_template, dst, svc_ctx)

    return {
        "phase": "implement",
        "steps": state.get("steps", 0) + 1,
        **journal(f"scaffold: wrote {files} files to {workspace.name} (template: microservice-monorepo)"),
    }
