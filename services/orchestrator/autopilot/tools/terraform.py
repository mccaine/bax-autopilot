"""Terraform driver for the deployer agent.

Default mode runs ``init -backend=false`` + ``validate`` + ``plan`` (no cloud
mutation, no creds needed). ``apply`` is gated behind ``AUTOPILOT_DEPLOY=apply``
*and* the presence of GCP credentials — a credential/cost gate, not a
human-approval gate.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from autopilot.config import Settings, get_settings


@dataclass
class TerraformResult:
    mode: str
    steps: list[tuple[str, int]] = field(default_factory=list)
    output: list[str] = field(default_factory=list)
    applied: bool = False

    @property
    def ok(self) -> bool:
        return all(code == 0 for _, code in self.steps)

    def summary(self, *, limit: int = 4000) -> str:
        tail = "\n".join(self.output)[-limit:]
        steps = ", ".join(f"{s}={c}" for s, c in self.steps)
        return f"[terraform {self.mode}] ok={self.ok} ({steps})\n{tail}"


def _run(tf_dir: Path, *args: str, env: dict) -> tuple[int, str]:
    p = subprocess.run(
        ["terraform", *args], cwd=tf_dir, capture_output=True, text=True, env=env, timeout=600
    )
    return p.returncode, (p.stdout + p.stderr)


def validate_and_plan(
    tf_dir: Path, *, settings: Settings | None = None
) -> TerraformResult:
    settings = settings or get_settings()
    tf_dir = Path(tf_dir).resolve()
    res = TerraformResult(mode=settings.deploy)

    env = {
        **os.environ,
        "TF_IN_AUTOMATION": "1",
        "TF_INPUT": "0",
        "TF_VAR_project_id": settings.gcp_project_id or "example-project",
        "TF_VAR_region": settings.gcp_region,
    }

    has_creds = bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
    want_apply = settings.deploy == "apply" and has_creds

    # Without creds we can still validate + plan against a fake backend.
    init_args = ("init", "-input=false") if want_apply else ("init", "-input=false", "-backend=false")

    for label, args in [
        ("init", init_args),
        ("validate", ("validate",)),
        ("plan", ("plan", "-input=false", "-no-color")),
    ]:
        code, out = _run(tf_dir, *args, env=env)
        res.steps.append((label, code))
        res.output.append(f"── {label} ──\n{out[-3000:]}")
        if code != 0:
            return res  # stop on first failure

    if want_apply:
        code, out = _run(tf_dir, "apply", "-input=false", "-auto-approve", "-no-color", env=env)
        res.steps.append(("apply", code))
        res.output.append(f"── apply ──\n{out[-3000:]}")
        res.applied = code == 0
    elif settings.deploy == "apply" and not has_creds:
        res.output.append("apply requested but GOOGLE_APPLICATION_CREDENTIALS unset — skipped.")

    return res
