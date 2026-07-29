"""Parallel coder fan-out: dispatch produces one Send per task and all tasks are
implemented in a single run."""

import json
import re
from types import SimpleNamespace as SN

from conftest import STACKS_DIR

from autopilot import graph as graph_mod
from autopilot.agents import base as base_mod
from autopilot.agents import scaffolder as scaffolder_mod
from autopilot.config import Settings
from autopilot.state import new_run_state
from autopilot.tools import compose as compose_mod
from autopilot.tools import git as git_mod
from autopilot.tools import terraform as tf_mod


class FanoutModel:
    def invoke(self, messages):
        text = " ".join(getattr(m, "content", str(m)) for m in messages)
        if "kebab-case-app-name" in text:
            return SN(content=json.dumps({
                "name": "multi", "summary": "s", "features": ["f"],
                "entities": [], "pages": ["/"], "acceptance_criteria": ["a"],
            }))
        if '"services"' in text and '"tasks"' in text:
            return SN(content=json.dumps({
                "services": [
                    {"name": "frontend", "kind": "frontend", "port": 3000},
                    {"name": "api", "kind": "service", "port": 4000},
                    {"name": "db", "kind": "db", "port": 5432},
                ],
                "tasks": [
                    {"id": "t1", "service": "api", "title": "alpha", "detail": "d"},
                    {"id": "t2", "service": "api", "title": "beta", "detail": "d"},
                    {"id": "t3", "service": "api", "title": "gamma", "detail": "d"},
                ],
            }))
        if '"approved"' in text:
            return SN(content=json.dumps({"approved": True, "notes": "ok"}))
        m = re.search(r"Task: (\w+)", text)
        title = m.group(1) if m else "x"
        return SN(content=json.dumps({f"services/api/src/{title}.ts": f"export const {title} = 1;\n"}))


def _ok(*a, **k):
    return compose_mod.ComposeResult("x", 0, "ok", "")


def test_dispatch_emits_one_send_per_task():
    sends = graph_mod._dispatch_implement(
        {"tasks": [{"id": "t1"}, {"id": "t2"}], "workspace": "/w", "spec": {}}
    )
    assert isinstance(sends, list) and len(sends) == 2
    assert all(s.node == "coder_worker" for s in sends)
    # No tasks → straight to test.
    assert graph_mod._dispatch_implement({"tasks": [], "workspace": "/w"}) == "test"


def test_all_tasks_implemented_in_one_run(monkeypatch, tmp_path):
    settings = Settings(provider="ollama", stacks_dir=STACKS_DIR, max_parallel_coders=3)
    monkeypatch.setattr(base_mod, "get_model", lambda *a, **k: FanoutModel())
    monkeypatch.setattr(scaffolder_mod, "get_settings", lambda: settings)
    monkeypatch.setattr(graph_mod, "get_settings", lambda: settings)
    monkeypatch.setattr(base_mod, "get_settings", lambda: settings)
    for name in ("build", "up", "down", "logs", "exec_test"):
        monkeypatch.setattr(compose_mod, name, _ok)
    monkeypatch.setattr(
        tf_mod, "validate_and_plan",
        lambda tf_dir, **k: SN(ok=True, mode="plan", applied=False, summary=lambda **kk: "ok"),
    )
    monkeypatch.setattr(
        git_mod, "init_commit_pr",
        lambda app_dir, **k: git_mod.GitResult(branch=k["branch"], committed=True, pr_url="http://pr"),
    )

    ws = tmp_path / "ws"
    ws.mkdir()
    state = new_run_state("rid", "multi task app")
    state["workspace"] = str(ws)

    graph = graph_mod.build_graph()
    final = graph.invoke(
        state, {"recursion_limit": 200, "max_concurrency": 3, "configurable": {"thread_id": "rid"}}
    )

    assert final["status"] == "done"
    # Every task produced its file (fan-out covered all three).
    for title in ("alpha", "beta", "gamma"):
        assert (ws / "services" / "api" / "src" / f"{title}.ts").exists()
    # The reducer accumulated one entry per worker.
    assert len(final.get("implemented", [])) == 3
