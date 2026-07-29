"""Project registry — one row per intent ("project").

Backed by Postgres (already in the compose stack) so the dashboard can list
projects and their status across orchestrator restarts. Falls back to an
in-memory store when the DB is unreachable (host dev / unit tests).
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

_STATUSES = ("queued", "running", "done", "blocked", "error")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Project:
    run_id: str
    intent: str
    status: str = "queued"
    name: str | None = None
    phase: str | None = None
    pr_url: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProjectStore:
    """Thin persistence over a `projects` table with an in-memory fallback."""

    def __init__(self, database_url: str) -> None:
        self._lock = threading.Lock()
        self._mem: dict[str, Project] = {}
        self._pool = None
        try:
            from psycopg_pool import ConnectionPool

            self._pool = ConnectionPool(database_url, min_size=1, max_size=4, open=True)
            self._init_schema()
        except Exception:
            self._pool = None  # in-memory fallback

    # ── schema ────────────────────────────────────────────────────────
    def _init_schema(self) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    run_id     TEXT PRIMARY KEY,
                    name       TEXT,
                    intent     TEXT NOT NULL,
                    status     TEXT NOT NULL,
                    phase      TEXT,
                    pr_url     TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )

    # ── writes ────────────────────────────────────────────────────────
    def create(self, run_id: str, intent: str) -> Project:
        p = Project(run_id=run_id, intent=intent, status="queued")
        if self._pool is None:
            with self._lock:
                self._mem[run_id] = p
            return p
        with self._pool.connection() as conn:
            conn.execute(
                "INSERT INTO projects (run_id, intent, status) VALUES (%s, %s, 'queued')",
                (run_id, intent),
            )
        return p

    def update(self, run_id: str, **fields: Any) -> None:
        fields = {k: v for k, v in fields.items() if k in {"name", "status", "phase", "pr_url"}}
        if not fields:
            return
        if self._pool is None:
            with self._lock:
                p = self._mem.get(run_id)
                if p:
                    for k, v in fields.items():
                        setattr(p, k, v)
                    p.updated_at = _now()
            return
        sets = ", ".join(f"{k} = %s" for k in fields)
        with self._pool.connection() as conn:
            conn.execute(
                f"UPDATE projects SET {sets}, updated_at = now() WHERE run_id = %s",
                (*fields.values(), run_id),
            )

    # ── reads ─────────────────────────────────────────────────────────
    def get(self, run_id: str) -> dict[str, Any] | None:
        if self._pool is None:
            with self._lock:
                p = self._mem.get(run_id)
                return p.to_dict() if p else None
        with self._pool.connection() as conn:
            cur = conn.execute("SELECT * FROM projects WHERE run_id = %s", (run_id,))
            row = cur.fetchone()
            return _row_to_dict(cur, row) if row else None

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        if self._pool is None:
            with self._lock:
                items = sorted(self._mem.values(), key=lambda p: p.created_at, reverse=True)
                return [p.to_dict() for p in items[:limit]]
        with self._pool.connection() as conn:
            cur = conn.execute(
                "SELECT * FROM projects ORDER BY created_at DESC LIMIT %s", (limit,)
            )
            return [_row_to_dict(cur, r) for r in cur.fetchall()]

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()


def _row_to_dict(cur, row) -> dict[str, Any]:
    cols = [d.name for d in cur.description]
    out = dict(zip(cols, row))
    for k in ("created_at", "updated_at"):
        if out.get(k) is not None:
            out[k] = out[k].isoformat()
    return out
