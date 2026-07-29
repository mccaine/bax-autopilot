"""Single-project concurrency: the runner's single worker never runs two
projects at once; queued intents run in order."""

import threading
import time

from autopilot.config import Settings
from autopilot.runner import Runner


class FakeGraph:
    """A graph stand-in whose `stream` blocks on a gate, so we can observe
    whether two runs ever execute concurrently."""

    def __init__(self) -> None:
        self.gate = threading.Event()
        self._lock = threading.Lock()
        self.concurrent = 0
        self.max_concurrent = 0

    def stream(self, state, config, stream_mode=None):
        with self._lock:
            self.concurrent += 1
            self.max_concurrent = max(self.max_concurrent, self.concurrent)
        self.gate.wait(timeout=5)
        with self._lock:
            self.concurrent -= 1
        yield {"status": "done", "phase": "done", "journal": ["ok"], "spec": {"name": "x"}}

    def get_state(self, cfg):
        return type("S", (), {"values": {}})()


def test_single_concurrency_and_ordering(tmp_path):
    runner = Runner(Settings(workspaces_dir=tmp_path / "ws", runs_dir=tmp_path / "runs"))
    fake = FakeGraph()
    runner.graph = fake  # swap the compiled graph for the blocking stand-in

    r1, pos1 = runner.enqueue("first")
    r2, pos2 = runner.enqueue("second")
    assert pos1 == 0  # nothing ahead

    # Wait until the worker has entered the first run.
    for _ in range(50):
        if fake.max_concurrent >= 1:
            break
        time.sleep(0.05)

    # While first is blocked, only one is running; second must still be queued.
    time.sleep(0.1)
    assert fake.concurrent == 1
    rows = {r["run_id"]: r for r in runner.list()}
    assert rows[r1].get("active") is True
    assert rows[r2]["status"] == "queued"

    # Release both runs.
    fake.gate.set()
    for _ in range(100):
        rows = {r["run_id"]: r for r in runner.list()}
        if rows[r1]["status"] == "done" and rows[r2]["status"] == "done":
            break
        time.sleep(0.05)

    assert rows[r1]["status"] == "done"
    assert rows[r2]["status"] == "done"
    # The key invariant: never more than one project running at a time.
    assert fake.max_concurrent == 1
    runner.close()
