"""Git + GitHub operations for the integrator agent.

Runs on the host-mounted workspace path via the git/gh CLIs baked into the
orchestrator image. PR creation is best-effort: if there is no remote or no
``GITHUB_TOKEN``, we still create the branch + commit and report that the PR
step was skipped.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from autopilot.config import Settings, get_settings


@dataclass
class GitResult:
    branch: str
    committed: bool
    pr_url: str | None = None
    skipped: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)


def _run(app_dir: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(args), cwd=app_dir, capture_output=True, text=True, env=env
    )


def init_commit_pr(
    app_dir: Path,
    *,
    branch: str,
    title: str,
    body: str,
    settings: Settings | None = None,
) -> GitResult:
    settings = settings or get_settings()
    app_dir = Path(app_dir).resolve()
    res = GitResult(branch=branch, committed=False)

    import os

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": settings.git_author_name,
        "GIT_AUTHOR_EMAIL": settings.git_author_email,
        "GIT_COMMITTER_NAME": settings.git_author_name,
        "GIT_COMMITTER_EMAIL": settings.git_author_email,
    }
    if settings.github_token:
        env["GH_TOKEN"] = settings.github_token

    def step(*args: str) -> subprocess.CompletedProcess:
        p = _run(app_dir, *args, env=env)
        res.log.append(f"$ {' '.join(args)} -> {p.returncode}")
        if p.stderr.strip():
            res.log.append(p.stderr.strip()[-500:])
        return p

    if not (app_dir / ".git").exists():
        step("git", "init", "-q")
    step("git", "checkout", "-B", branch)
    step("git", "add", "-A")
    commit = step("git", "commit", "-q", "-m", title)
    res.committed = commit.returncode == 0
    if not res.committed:
        res.skipped.append("commit (nothing to commit?)")

    # PR needs a remote + auth; skip cleanly otherwise.
    has_remote = _run(app_dir, "git", "remote").stdout.strip() != ""
    if not settings.github_token:
        res.skipped.append("pr (no GITHUB_TOKEN)")
        return res
    if not has_remote:
        res.skipped.append("pr (no git remote configured)")
        return res

    step("git", "push", "-u", "origin", branch, "--force")
    pr = step("gh", "pr", "create", "--title", title, "--body", body, "--head", branch)
    if pr.returncode == 0:
        res.pr_url = pr.stdout.strip()
    else:
        res.skipped.append("pr (gh pr create failed)")
    return res
