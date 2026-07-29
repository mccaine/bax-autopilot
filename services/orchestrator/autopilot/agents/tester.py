"""Tester agent: bring the generated stack up and exercise it.

Builds images, ``docker compose up --wait`` (blocks on healthchecks), then runs
the app's own test target. The pass/fail here is the machine gate that drives the
build→fix loop.
"""

from __future__ import annotations

from autopilot.agents.base import journal, workspace_for
from autopilot.tools import compose


def test_node(state: dict) -> dict:
    ws = workspace_for(state)
    app_dir = ws.root

    reports: list[str] = []
    ok = True

    build = compose.build(app_dir)
    reports.append(build.summary())
    if not build.ok:
        ok = False
    else:
        up = compose.up(app_dir, wait=True)
        reports.append(up.summary())
        if not up.ok:
            ok = False
            reports.append(compose.logs(app_dir).summary())
        else:
            # Run the app's test target if it defines one; else the healthy
            # compose --wait is itself the smoke test.
            test = compose.exec_test(app_dir, "api", "npm test --silent || true")
            reports.append(test.summary())
            # A failing `npm test` sets exit!=0 only if we drop the `|| true`;
            # keep the loop conservative: treat non-zero test as failure.
            strict = compose.exec_test(app_dir, "api", "npm test --silent")
            if not strict.ok:
                ok = False
                reports.append(strict.summary())
        compose.down(app_dir)

    return {
        "test_ok": ok,
        "test_report": "\n\n".join(reports)[-8000:],
        "phase": "review" if ok else "fix",
        "steps": state.get("steps", 0) + 1,
        **journal(f"test: {'PASS' if ok else 'FAIL'}"),
    }
