"""Tester agent: bring the generated stack up and exercise it.

Builds images, ``docker compose up --wait`` (blocks on healthchecks), then runs
each Node service's tests. The pass/fail here is the machine gate that drives the
build→fix loop.

On failure it captures the build output, compose logs, and test output into
``state['test_report']`` (fed to the fixer) and also writes them to
``<workspace>/.autopilot/test-report.txt`` so a human can inspect the exact error.
"""

from __future__ import annotations

from autopilot.agents.base import journal, workspace_for
from autopilot.tools import compose


def _node_services(state: dict) -> list[str]:
    names = [s["name"] for s in state.get("services", []) if s.get("kind") == "service"]
    return names or ["api"]


def test_node(state: dict) -> dict:
    ws = workspace_for(state)
    app_dir = ws.root

    reports: list[str] = []
    ok = True
    reason = ""

    build = compose.build(app_dir)
    reports.append(build.summary())
    if not build.ok:
        ok, reason = False, "image build failed"
    else:
        up = compose.up(app_dir, wait=True)
        reports.append(up.summary())
        if not up.ok:
            ok, reason = False, "stack did not become healthy"
            reports.append(compose.logs(app_dir).summary())
        else:
            for svc in _node_services(state):
                t = compose.exec_test(app_dir, svc, "npm test --silent")
                reports.append(t.summary())
                if not t.ok:
                    ok, reason = False, f"{svc} tests failed"
            if not ok:
                reports.append(compose.logs(app_dir).summary())
        compose.down(app_dir)

    report = "\n\n".join(reports)[-12000:]
    # Persist the full report alongside the project for human inspection.
    try:
        ws.write(".autopilot/test-report.txt", report)
    except Exception:
        pass

    line = "test: PASS" if ok else f"test: FAIL — {reason}"
    return {
        "test_ok": ok,
        "test_report": report,
        "phase": "review" if ok else "fix",
        "steps": state.get("steps", 0) + 1,
        **journal(line),
    }
