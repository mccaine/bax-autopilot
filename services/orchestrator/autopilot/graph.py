"""The LangGraph state machine that wires the agents together.

Linear spine: spec → architect → scaffold → implement → test.
Loop: test/review failures route to `fix` → test, bounded by AUTOPILOT_MAX_FIX_ITERS
and the global step budget. When a budget is blown the run ends `blocked` with a
report rather than looping forever.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from autopilot.agents import (
    architect_node,
    coder_worker_node,
    deploy_node,
    fix_node,
    integrate_node,
    review_node,
    scaffold_node,
    spec_node,
    test_node,
)
from autopilot.agents.base import budgets_exhausted
from autopilot.config import get_settings
from autopilot.state import RunState


def _blocked_node(state: dict) -> dict:
    reason = budgets_exhausted(state) or "iteration cap reached"
    return {
        "status": "blocked",
        "phase": "blocked",
        "error": reason,
        "journal": [f"BLOCKED: {reason}"],
    }


def _dispatch_implement(state: dict):
    """Fan out one `coder_worker` per task (parallel), or skip to `test` if there
    are no tasks. Each Send carries only what a worker needs — the worker returns
    reducer-merged results into the shared state."""
    tasks = [t for t in state.get("tasks", []) if not t.get("done")]
    if not tasks:
        return "test"
    return [
        Send(
            "coder_worker",
            {
                "workspace": state["workspace"],
                "spec": state.get("spec", {}),
                "current_task": t,
            },
        )
        for t in tasks
    ]


def _route_after_test(state: dict) -> str:
    if budgets_exhausted(state):
        return "blocked"
    if state.get("test_ok"):
        return "review"
    if state.get("fix_iters", 0) >= get_settings().max_fix_iters:
        return "blocked"
    return "fix"


def _route_after_review(state: dict) -> str:
    if budgets_exhausted(state):
        return "blocked"
    if state.get("review_ok"):
        return "deploy"
    if state.get("fix_iters", 0) >= get_settings().max_fix_iters:
        return "blocked"
    return "fix"


def build_graph(checkpointer=None):
    """Construct and compile the run graph. Pass a checkpointer (Postgres in
    prod, MemorySaver in tests) for resumability; None compiles without one."""
    g = StateGraph(RunState)

    g.add_node("spec", spec_node)
    g.add_node("architect", architect_node)
    g.add_node("scaffold", scaffold_node)
    g.add_node("coder_worker", coder_worker_node)
    g.add_node("test", test_node)
    g.add_node("review", review_node)
    g.add_node("fix", fix_node)
    g.add_node("deploy", deploy_node)
    g.add_node("integrate", integrate_node)
    g.add_node("blocked", _blocked_node)

    g.add_edge(START, "spec")
    g.add_edge("spec", "architect")
    g.add_edge("architect", "scaffold")
    # Fan out: scaffold → N parallel coder_workers (or straight to test if no tasks).
    g.add_conditional_edges("scaffold", _dispatch_implement, ["coder_worker", "test"])
    # Join: all workers in the superstep complete, then test runs once.
    g.add_edge("coder_worker", "test")

    g.add_conditional_edges(
        "test", _route_after_test, {"review": "review", "fix": "fix", "blocked": "blocked"}
    )
    g.add_conditional_edges(
        "review", _route_after_review, {"deploy": "deploy", "fix": "fix", "blocked": "blocked"}
    )
    g.add_edge("fix", "test")
    g.add_edge("deploy", "integrate")
    g.add_edge("integrate", END)
    g.add_edge("blocked", END)

    return g.compile(checkpointer=checkpointer)
