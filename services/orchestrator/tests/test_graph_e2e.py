"""End-to-end graph run with the LLM and all side-effecting tools mocked.

Proves the spine + routing + scaffold rendering + agent wiring reach `done` and
produce a real (rendered) workspace, without needing Ollama or Docker.
"""

import json
from pathlib import Path
from types import SimpleNamespace

from conftest import STACKS_DIR

from autopilot import graph as graph_mod
from autopilot.agents import base as base_mod
from autopilot.agents import scaffolder as scaffolder_mod
from autopilot.config import Settings
from autopilot.state import new_run_state
from autopilot.tools import compose as compose_mod
from autopilot.tools import git as git_mod
from autopilot.tools import terraform as tf_mod


class FakeModel:
    """Returns canned JSON depending on which agent's prompt it sees."""

    def invoke(self, messages):
        text = " ".join(getattr(m, "content", str(m)) for m in messages)
        if "kebab-case-app-name" in text:  # spec
            return SimpleNamespace(content=json.dumps({
                "name": "todo-app", "summary": "manage tasks",
                "features": ["crud tasks"], "entities": [], "pages": ["/"],
                "acceptance_criteria": ["builds", "healthz 200"],
            }))
        if '"services"' in text and '"tasks"' in text:  # architect
            return SimpleNamespace(content=json.dumps({
                "services": [
                    {"name": "frontend", "kind": "frontend", "port": 3000},
                    {"name": "api", "kind": "service", "port": 4000},
                    {"name": "db", "kind": "db", "port": 5432},
                ],
                "tasks": [{"id": "t1", "service": "api", "title": "tasks CRUD", "detail": "x"}],
            }))
        if '"approved"' in text:  # reviewer
            return SimpleNamespace(content=json.dumps({"approved": True, "notes": "ok"}))
        # coder / fixer → a file map
        return SimpleNamespace(content=json.dumps({
            "services/api/src/tasks.ts": "export const tasks = [];\n"
        }))


def _ok_compose(*a, **k):
    return compose_mod.ComposeResult("x", 0, "ok", "")


def test_full_run_reaches_done(monkeypatch, tmp_path):
    settings = Settings(
        provider="ollama",
        stacks_dir=STACKS_DIR,
        max_fix_iters=6,
        step_budget=100,
        deploy="plan",
    )
    # LLM
    monkeypatch.setattr(base_mod, "get_model", lambda *a, **k: FakeModel())
    # scaffolder uses real template but test settings for stacks_dir
    monkeypatch.setattr(scaffolder_mod, "get_settings", lambda: settings)
    # graph + base budget checks
    monkeypatch.setattr(graph_mod, "get_settings", lambda: settings)
    monkeypatch.setattr(base_mod, "get_settings", lambda: settings)
    # tools: compose all-green, terraform ok, git makes a PR
    for name in ("build", "up", "down", "logs", "exec_test"):
        monkeypatch.setattr(compose_mod, name, _ok_compose)
    monkeypatch.setattr(
        tf_mod, "validate_and_plan",
        lambda tf_dir, **k: SimpleNamespace(
            ok=True, mode="plan", applied=False, summary=lambda **kk: "plan ok"
        ),
    )
    monkeypatch.setattr(
        git_mod, "init_commit_pr",
        lambda app_dir, **k: git_mod.GitResult(
            branch=k["branch"], committed=True, pr_url="http://example/pr/1"
        ),
    )

    ws = tmp_path / "ws"
    ws.mkdir()
    state = new_run_state("rid1234", "a todo app with a tasks API")
    state["workspace"] = str(ws)

    graph = graph_mod.build_graph()
    final = graph.invoke(state, {"recursion_limit": 200, "configurable": {"thread_id": "rid1234"}})

    # Reached the end cleanly.
    assert final["status"] == "done"
    assert final["phase"] == "done"
    assert final["test_ok"] is True
    assert final["review_ok"] is True
    assert final["pr_url"] == "http://example/pr/1"

    # Scaffold actually rendered the template into the workspace.
    assert (ws / "docker-compose.yml").exists()
    assert (ws / "Makefile").exists()
    assert (ws / "services" / "api" / "package.json").exists()
    assert (ws / "services" / "api" / "src" / "index.ts").exists()
    assert (ws / "infra" / "terraform" / "main.tf").exists()
    # Coder wrote its file.
    assert (ws / "services" / "api" / "src" / "tasks.ts").exists()

    # Rendered values are present (jinja ran).
    compose_txt = (ws / "docker-compose.yml").read_text()
    assert "api:" in compose_txt and "db:" in compose_txt
    assert "{{" not in (ws / "services" / "api" / "src" / "index.ts").read_text()
