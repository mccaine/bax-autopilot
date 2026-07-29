"""Run a generated app's own docker-compose stack (frontend + services + db).

Unlike :mod:`shell` (a throwaway sandbox container per command), the generated
app is a multi-service system we bring *up*, health-check, test against, and
tear down. We drive the host docker daemon via the mounted socket, using the
workspace path directly (mirrored between host and orchestrator container).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ComposeResult:
    action: str
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def summary(self, *, limit: int = 6000) -> str:
        return (
            f"[compose {self.action}] exit={self.exit_code}\n"
            f"{(self.stdout or '')[-limit:]}\n{(self.stderr or '')[-limit:]}"
        ).strip()


def _compose(app_dir: Path, *args: str, timeout: int = 1200) -> ComposeResult:
    app_dir = Path(app_dir).resolve()
    # A stable project name keeps `up`/`down`/`ps` referring to the same stack.
    project = f"autopilot-{app_dir.name}".lower().replace("_", "-")
    cmd = ["docker", "compose", "-p", project, *args]
    try:
        proc = subprocess.run(
            cmd, cwd=app_dir, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as e:
        return ComposeResult(" ".join(args), 124, e.stdout or "", f"timeout after {timeout}s")
    return ComposeResult(" ".join(args), proc.returncode, proc.stdout, proc.stderr)


def build(app_dir: Path) -> ComposeResult:
    return _compose(app_dir, "build")


def up(app_dir: Path, *, wait: bool = True) -> ComposeResult:
    args = ["up", "-d"]
    if wait:
        # --wait blocks until healthchecks pass (or fail).
        args.append("--wait")
    return _compose(app_dir, *args, timeout=1800)


def down(app_dir: Path) -> ComposeResult:
    return _compose(app_dir, "down", "-v")


def logs(app_dir: Path, *, tail: int = 200) -> ComposeResult:
    return _compose(app_dir, "logs", "--no-color", f"--tail={tail}")


def ps(app_dir: Path) -> ComposeResult:
    return _compose(app_dir, "ps")


def exec_test(app_dir: Path, service: str, command: str) -> ComposeResult:
    """Run a test command inside an already-running service container."""
    return _compose(app_dir, "exec", "-T", service, "sh", "-lc", command, timeout=1200)
