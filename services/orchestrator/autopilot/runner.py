"""Run lifecycle with **single-project concurrency**.

A single worker thread drains a FIFO queue, so at most one project ever runs.
New intents are accepted immediately and queued. Project rows are persisted in
Postgres (see store.py) so the dashboard can list running/queued/history; live
phase + journal come from the LangGraph checkpointer.
"""

from __future__ import annotations

import queue
import threading
import uuid
from pathlib import Path
from typing import Any

from autopilot.config import Settings, get_settings
from autopilot.graph import build_graph
from autopilot.state import new_run_state
from autopilot.store import ProjectStore

RECURSION_LIMIT = 200
_SENTINEL = None


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
        self.store = ProjectStore(self.settings.database_url)

        self._queue: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._pending: list[str] = []  # ordered run_ids awaiting the worker
        self._active: str | None = None
        self._stop = False
        self._worker = threading.Thread(target=self._run_loop, name="autopilot-worker", daemon=True)
        self._worker.start()

    # ── enqueue ───────────────────────────────────────────────────────
    def enqueue(self, intent: str) -> tuple[str, int]:
        """Create a project, queue it, return (run_id, queue_position). Position
        0 means it will start immediately (nothing running/ahead)."""
        run_id = uuid.uuid4().hex
        self.store.create(run_id, intent)
        with self._lock:
            self._pending.append(run_id)
            position = len(self._pending) - 1 + (1 if self._active else 0)
        self._queue.put((run_id, intent))
        return run_id, position

    # ── single worker: at most one project runs at a time ─────────────
    def _run_loop(self) -> None:
        while not self._stop:
            item = self._queue.get()
            if item is _SENTINEL:
                break
            run_id, intent = item
            with self._lock:
                if run_id in self._pending:
                    self._pending.remove(run_id)
                self._active = run_id
            try:
                self._execute(run_id, intent)
            except Exception as e:  # noqa: BLE001
                self.store.update(run_id, status="error", phase="error")
                self._write_journal(run_id, [f"ERROR: {e}"])
            finally:
                with self._lock:
                    self._active = None
                self._queue.task_done()

    def _execute(self, run_id: str, intent: str) -> None:
        ws = Path(self.settings.workspaces_dir) / run_id
        ws.mkdir(parents=True, exist_ok=True)
        state = new_run_state(run_id, intent)
        state["workspace"] = str(ws)
        config = {
            "recursion_limit": RECURSION_LIMIT,
            "max_concurrency": self.settings.max_parallel_coders,
            "configurable": {"thread_id": run_id},
        }
        self.store.update(run_id, status="running", phase="spec")

        last: dict[str, Any] = {}
        last_phase = "spec"
        # Stream so we can persist live phase (and derive the project name once
        # the spec node names it) as the graph progresses.
        for chunk in self.graph.stream(state, config, stream_mode="values"):
            last = chunk
            phase = chunk.get("phase")
            name = chunk.get("spec", {}).get("name") if chunk.get("spec") else None
            updates: dict[str, Any] = {}
            if phase and phase != last_phase:
                updates["phase"] = phase
                last_phase = phase
            if name:
                updates["name"] = name
            if updates:
                self.store.update(run_id, **updates)

        self.store.update(
            run_id,
            status=last.get("status", "done"),
            phase=last.get("phase", "done"),
            pr_url=last.get("pr_url"),
            name=(last.get("spec", {}) or {}).get("name"),
        )
        self._write_journal(run_id, last.get("journal", []))

    # ── introspection ─────────────────────────────────────────────────
    def status(self, run_id: str) -> dict[str, Any] | None:
        base = self.store.get(run_id)
        if base is None:
            return None
        with self._lock:
            if run_id in self._pending:
                base["queue_position"] = self._pending.index(run_id) + (1 if self._active else 0)
        # Live detail from the checkpointer (journal, exact phase, counters).
        try:
            st = self.graph.get_state({"configurable": {"thread_id": run_id}})
            if st and st.values:
                v = st.values
                base.update(
                    phase=v.get("phase", base.get("phase")),
                    steps=v.get("steps", 0),
                    fix_iters=v.get("fix_iters", 0),
                    implemented=v.get("implemented", []),
                    journal=v.get("journal", [])[-60:],
                    pr_url=v.get("pr_url", base.get("pr_url")),
                )
        except Exception:
            pass
        return base

    def list(self) -> list[dict[str, Any]]:
        rows = self.store.list()
        with self._lock:
            pending = list(self._pending)
            active = self._active
        for r in rows:
            if r["run_id"] == active:
                r["active"] = True
            elif r["run_id"] in pending:
                r["queue_position"] = pending.index(r["run_id"]) + (1 if active else 0)
        return rows

    # ── housekeeping ──────────────────────────────────────────────────
    def _write_journal(self, run_id: str, lines: list[str]) -> None:
        try:
            runs_dir = Path(self.settings.runs_dir)
            runs_dir.mkdir(parents=True, exist_ok=True)
            (runs_dir / f"{run_id}.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:
            pass

    def close(self) -> None:
        self._stop = True
        self._queue.put(_SENTINEL)
        self.store.close()
        if self._closer is not None:
            try:
                self._closer.__exit__(None, None, None)
            except Exception:
                pass
