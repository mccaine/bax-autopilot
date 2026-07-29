"""Deployer agent: validate the generated Terraform (and optionally apply).

The stack template ships ``infra/terraform`` (Cloud Run per service + Cloud SQL +
Artifact Registry). Here we run terraform validate + plan; a real ``apply`` only
happens when AUTOPILOT_DEPLOY=apply and GCP creds are present (see
tools/terraform.py).
"""

from __future__ import annotations

from autopilot.agents.base import journal, workspace_for
from autopilot.tools import terraform


def deploy_node(state: dict) -> dict:
    ws = workspace_for(state)
    tf_dir = ws.root / "infra" / "terraform"

    if not tf_dir.exists():
        return {
            "deploy_ok": False,
            "deploy_report": "no infra/terraform in generated app",
            "phase": "integrate",
            "steps": state.get("steps", 0) + 1,
            **journal("deploy: skipped (no terraform)"),
        }

    result = terraform.validate_and_plan(tf_dir)
    return {
        "deploy_ok": result.ok,
        "deploy_report": result.summary(),
        "phase": "integrate",
        "steps": state.get("steps", 0) + 1,
        **journal(f"deploy: terraform {result.mode} ok={result.ok} applied={result.applied}"),
    }
