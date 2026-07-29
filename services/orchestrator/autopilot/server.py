"""FastAPI control surface for the orchestrator.

    POST /runs        {"intent": "..."}   → {"run_id", "status", "position"}
    GET  /runs                             → project list (running/queued/history)
    GET  /runs/{id}                        → status snapshot (phase, journal, pr_url)
    GET  /healthz                          → liveness
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from autopilot.runner import Runner


class RunRequest(BaseModel):
    intent: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.runner = Runner()
    try:
        yield
    finally:
        app.state.runner.close()


app = FastAPI(title="BAX Autopilot", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/runs")
def create_run(req: RunRequest) -> dict:
    if not req.intent.strip():
        raise HTTPException(status_code=422, detail="intent is required")
    run_id, position = app.state.runner.enqueue(req.intent.strip())
    return {"run_id": run_id, "status": "queued", "position": position}


@app.get("/runs")
def list_runs() -> dict:
    return {"projects": app.state.runner.list()}


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    snapshot = app.state.runner.status(run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="unknown run")
    return snapshot
