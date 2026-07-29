"""Run lifecycle: build the graph, kick off a run in the background, expose status.

State is persisted by the LangGraph checkpointer (Postgres in prod, Memory as a
fallback), keyed by ``thread_id == run_id``, so status survives across requests
and runs are resumable.
"""

from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any

from autopilot.config import Settings, get_settings
from autopilot.graph import build_graph
from autopilot.state import new_run_state

# Allow enough graph super-steps for several fix-loop iterations.
RECURSION_LIMIT = 200


def make_checkpointer(settings: Settings):
    """Return (checkpointer, closer). Falls back to in-memory if Postgres is
    unreachable (e.g. local dev without the compose db)."""
    try:
        from langgraph.checkpoint.postgres import PostgresSaver

        cm = PostgresSaver.from_conn_string(settings.database_url)
        saver = cm.__enter__()
        saver.setup()
        return saver, cm
    except Exception:
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver(), None


class Runner:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.checkpointer, self._closer = make_checkpointer(self.settings)
        self.graph = build_graph(self.checkpointer)
        # Best-effort mirror for immediate status before the first checkpoint.
        self._status: dict[str, dict[str, Any]] = {}

    # ── lifecycle ─────────────────────────────────────────────────────
    def start(self, intent: str) -> str:
        run_id = uuid.uuid4().hex
        ws = Path(self.settings.workspaces_dir) / run_id
        ws.mkdir(parents=True, exist_ok=True)

        state = new_run_state(run_id, intent)
        state["workspace"] = str(ws)
        config = {"configurable": {"thread_id": run_id}, "recursion_limit": RECURSION_LIMIT}
        self._status[run_id] = {"status": "running", "phase": "spec"}

        def worker() -> None:
            try:
                final = self.graph.invoke(state, config)
                self._status[run_id] = {
                    "status": final.get("status", "done"),
                    "phase": final.get("phase", "done"),
                }
                self._write_journal(run_id, final)
            except Exception as e:  # noqa: BLE001 — surface any failure as run status
                self._status[run_id] = {"status": "error", "phase": "error", "error": str(e)}

        threading.Thread(target=worker, name=f"run-{run_id}", daemon=True).start()
        return run_id

    # ── introspection ─────────────────────────────────────────────────
    def status(self, run_id: str) -> dict[str, Any] | None:
        snapshot: dict[str, Any] = dict(self._status.get(run_id, {}))
        try:
            cfg = {"configurable": {"thread_id": run_id}}
            st = self.graph.get_state(cfg)
            if st and st.values:
                v = st.values
                snapshot.update(
                    status=v.get("status", snapshot.get("status", "running")),
                    phase=v.get("phase", snapshot.get("phase")),
                    steps=v.get("steps", 0),
                    fix_iters=v.get("fix_iters", 0),
                    pr_url=v.get("pr_url"),
                    journal=v.get("journal", [])[-40:],
                    error=v.get("error"),
                )
        except Exception:
            pass
        if not snapshot:
            return None
        snapshot["run_id"] = run_id
        return snapshot

    def _write_journal(self, run_id: str, final: dict) -> None:
        try:
            runs_dir = Path(self.settings.runs_dir)
            runs_dir.mkdir(parents=True, exist_ok=True)
            lines = final.get("journal", [])
            (runs_dir / f"{run_id}.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:
            pass

    def close(self) -> None:
        if self._closer is not None:
            try:
                self._closer.__exit__(None, None, None)
            except Exception:
                pass
