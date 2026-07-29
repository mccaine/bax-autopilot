"""API surface: enqueue, list, detail, 404 — with a stub runner."""

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from autopilot import server  # noqa: E402


class StubRunner:
    def __init__(self):
        self._p = {}

    def enqueue(self, intent):
        rid = "run-" + str(len(self._p) + 1)
        self._p[rid] = {"run_id": rid, "intent": intent, "status": "queued"}
        return rid, len(self._p) - 1

    def list(self):
        return list(self._p.values())

    def status(self, rid):
        return self._p.get(rid)

    def close(self):
        pass


def test_api_flow(monkeypatch):
    monkeypatch.setattr(server, "Runner", StubRunner)
    with TestClient(server.app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}

        r = client.post("/runs", json={"intent": "a todo app"})
        assert r.status_code == 200
        run_id = r.json()["run_id"]
        assert r.json()["status"] == "queued"

        listing = client.get("/runs").json()["projects"]
        assert any(p["run_id"] == run_id for p in listing)

        detail = client.get(f"/runs/{run_id}")
        assert detail.status_code == 200
        assert detail.json()["intent"] == "a todo app"

        assert client.get("/runs/nope").status_code == 404

        # empty intent rejected
        assert client.post("/runs", json={"intent": "   "}).status_code == 422
