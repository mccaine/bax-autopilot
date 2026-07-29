"""Sandboxed command execution.

All generated-code commands run inside a throwaway Docker container with the
workspace mounted — never on the host. A conservative allowlist gates which
executables may run, and every call is bounded by a timeout.

Because the orchestrator itself runs in a container with the Docker socket
mounted (docker-out-of-docker), we shell out to the ``docker`` CLI. The
workspace path is identical on host and in the orchestrator container (see the
compose volume mount), so bind-mounting it into a sibling container works.
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Executables the agents are permitted to invoke inside the sandbox. Anything
# else is refused before it reaches Docker.
DEFAULT_ALLOWLIST = frozenset(
    {
        "node", "npm", "npx", "pnpm", "yarn",
        "python", "python3", "pip",
        "pytest", "jest", "vitest", "playwright",
        "psql", "pg_isready",
        "sh", "bash", "make",
        "ls", "cat", "echo", "true", "test",
        "prisma", "tsc", "eslint",
    }
)

# Default sandbox image: node + a little python, enough to build/test a
# Next.js + Node service monorepo. Overridable per call.
DEFAULT_IMAGE = "node:20-bookworm"


@dataclass
class ExecResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def summary(self, *, limit: int = 4000) -> str:
        out = (self.stdout or "")[-limit:]
        err = (self.stderr or "")[-limit:]
        return f"$ {self.command}\n[exit {self.exit_code}]\n{out}\n{err}".strip()


class SandboxError(RuntimeError):
    pass


def _check_allowed(command: str, allowlist: frozenset[str]) -> None:
    try:
        tokens = shlex.split(command)
    except ValueError as e:
        raise SandboxError(f"un-parseable command: {command!r} ({e})") from e
    if not tokens:
        raise SandboxError("empty command")
    exe = Path(tokens[0]).name
    if exe not in allowlist:
        raise SandboxError(f"command not allowed in sandbox: {exe!r}")


def run_in_sandbox(
    command: str,
    *,
    workdir: Path,
    image: str = DEFAULT_IMAGE,
    timeout: int = 900,
    allowlist: frozenset[str] = DEFAULT_ALLOWLIST,
    network: str = "bridge",
    extra_docker_args: list[str] | None = None,
) -> ExecResult:
    """Run ``command`` inside a fresh container with ``workdir`` mounted at /work.

    ``workdir`` must be an absolute host path (identical inside the orchestrator
    container thanks to the mirrored compose mount).
    """
    _check_allowed(command, allowlist)
    workdir = Path(workdir).resolve()

    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{workdir}:/work",
        "-w", "/work",
        "--network", network,
        *(extra_docker_args or []),
        image,
        "sh", "-lc", command,
    ]
    try:
        proc = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        return ExecResult(command, 124, e.stdout or "", f"timeout after {timeout}s")
    except FileNotFoundError as e:  # docker CLI missing
        raise SandboxError(f"docker CLI unavailable: {e}") from e

    return ExecResult(command, proc.returncode, proc.stdout, proc.stderr)
