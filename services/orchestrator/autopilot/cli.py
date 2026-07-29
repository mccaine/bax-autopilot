"""Local CLI for running a build without the HTTP server (host dev / debugging).

    autopilot build "a todo app with auth"
    autopilot graph            # print the graph structure
"""

from __future__ import annotations

import uuid
from pathlib import Path

import typer
from rich.console import Console

from autopilot.config import get_settings
from autopilot.graph import build_graph
from autopilot.state import new_run_state

app = typer.Typer(add_completion=False, help="BAX Autopilot")
console = Console()


@app.command()
def build(intent: str) -> None:
    """Run the full pipeline for INTENT and print the journal."""
    settings = get_settings()
    run_id = uuid.uuid4().hex
    ws = Path(settings.workspaces_dir) / run_id
    ws.mkdir(parents=True, exist_ok=True)

    state = new_run_state(run_id, intent)
    state["workspace"] = str(ws)

    graph = build_graph()  # no checkpointer for a one-shot local run
    console.print(f"[bold]run[/bold] {run_id} → {ws}")
    final = graph.invoke(
        state,
        {
            "recursion_limit": 200,
            "max_concurrency": settings.max_parallel_coders,
            "configurable": {"thread_id": run_id},
        },
    )

    console.rule("journal")
    for line in final.get("journal", []):
        console.print(line)
    console.rule("result")
    console.print(
        f"status={final.get('status')} phase={final.get('phase')} "
        f"pr={final.get('pr_url')} tests={'ok' if final.get('test_ok') else 'fail'}"
    )


@app.command()
def graph() -> None:
    """Print the compiled graph (ASCII)."""
    g = build_graph()
    try:
        console.print(g.get_graph().draw_ascii())
    except Exception:
        console.print("nodes:", list(g.get_graph().nodes))


if __name__ == "__main__":
    app()
