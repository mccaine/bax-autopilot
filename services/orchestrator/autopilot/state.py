"""The graph's shared state.

A single ``RunState`` flows through every node. LangGraph merges each node's
returned partial dict into it, and the Postgres checkpointer persists it after
every step so runs are resumable and inspectable.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

Phase = Literal[
    "spec", "architect", "scaffold", "implement",
    "test", "review", "fix", "deploy", "integrate", "done", "blocked",
]

Status = Literal["running", "done", "blocked", "error"]


class ServiceSpec(TypedDict, total=False):
    name: str
    kind: Literal["frontend", "service", "db"]
    description: str
    port: int


class Task(TypedDict, total=False):
    id: str
    service: str
    title: str
    detail: str
    done: bool


class RunState(TypedDict, total=False):
    # ── inputs ────────────────────────────────────────────────────────
    run_id: str
    intent: str

    # ── produced artifacts ────────────────────────────────────────────
    spec: dict[str, Any]           # structured product spec
    services: list[ServiceSpec]    # service decomposition
    tasks: list[Task]              # ordered implementation tasks
    workspace: str                 # absolute path to workspaces/<run-id>

    # Fan-out: the single task a coder_worker was dispatched to implement.
    current_task: Task
    # Concurrent-safe accumulator of per-worker results ("t1:+3 files").
    implemented: Annotated[list[str], operator.add]

    # ── loop bookkeeping ──────────────────────────────────────────────
    phase: Phase
    status: Status
    fix_iters: int
    steps: int                     # total node visits (against step_budget)
    tokens: int                    # cumulative (best-effort) token estimate

    # ── latest results (overwritten each pass) ────────────────────────
    test_ok: bool
    test_report: str
    review_ok: bool
    review_notes: str
    deploy_ok: bool
    deploy_report: str
    pr_url: str | None

    # ── observability: append-only log (reducer merges lists) ─────────
    journal: Annotated[list[str], operator.add]
    error: str | None


def new_run_state(run_id: str, intent: str) -> RunState:
    return RunState(
        run_id=run_id,
        intent=intent,
        phase="spec",
        status="running",
        fix_iters=0,
        steps=0,
        tokens=0,
        test_ok=False,
        review_ok=False,
        deploy_ok=False,
        pr_url=None,
        implemented=[],
        journal=[],
        error=None,
    )
