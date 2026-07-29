"""Central configuration, loaded from environment / .env.

Every knob the harness exposes lives here so the rest of the code depends on a
typed object, not on os.environ scattered around.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Role = Literal["coder", "planner", "router"]
Provider = Literal["ollama", "anthropic"]


class Settings(BaseSettings):
    """Typed view of the environment. Prefix everything with AUTOPILOT_ where
    it is ours; a few well-known names (ANTHROPIC_API_KEY, DATABASE_URL, GCP_*)
    are read as-is."""

    model_config = SettingsConfigDict(
        env_prefix="AUTOPILOT_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Provider selection ────────────────────────────────────────────
    provider: Provider = "ollama"
    # Optional per-role provider override (e.g. AUTOPILOT_PROVIDER_CODER=anthropic).
    provider_coder: Provider | None = None
    provider_planner: Provider | None = None
    provider_router: Provider | None = None

    # ── Local (Ollama) model roster ───────────────────────────────────
    ollama_host: str = Field(
        default="http://host.docker.internal:11434", validation_alias="OLLAMA_HOST"
    )
    model_coder: str = "qwen2.5-coder:32b"
    model_planner: str = "qwen2.5:32b-instruct"
    model_router: str = "llama3.2:3b"

    # ── Cloud (Anthropic) model roster ────────────────────────────────
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    anthropic_model_coder: str = "claude-sonnet-5"
    anthropic_model_planner: str = "claude-opus-4-8"
    anthropic_model_router: str = "claude-haiku-4-5"

    # ── Autonomy budgets (hard caps; the loop aborts cleanly at these) ─
    max_fix_iters: int = 6
    step_budget: int = 120
    token_budget: int = 0  # 0 = unlimited

    # Bound on parallel coder workers (one GPU serves Ollama — keep modest).
    max_parallel_coders: int = 3

    # Fast self-check: after patching, the fixer rebuilds (no up/test) and may
    # re-patch this many times against the build error before the full test run.
    fix_inner_retries: int = 2

    # ── Deploy gate ───────────────────────────────────────────────────
    deploy: Literal["plan", "apply"] = "plan"

    # ── GCP defaults threaded into generated Terraform ────────────────
    gcp_project_id: str = Field(default="", validation_alias="GCP_PROJECT_ID")
    gcp_region: str = Field(default="us-central1", validation_alias="GCP_REGION")

    # ── Infra ─────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql://autopilot:autopilot@postgres:5432/autopilot",
        validation_alias="DATABASE_URL",
    )
    workspaces_dir: Path = Path("/app/workspaces")
    runs_dir: Path = Path("/app/runs")
    stacks_dir: Path = Path("/app/stacks")

    # ── Git ───────────────────────────────────────────────────────────
    github_token: str = Field(default="", validation_alias="GITHUB_TOKEN")
    git_author_name: str = Field(default="bax-autopilot", validation_alias="GIT_AUTHOR_NAME")
    git_author_email: str = Field(
        default="autopilot@bax.local", validation_alias="GIT_AUTHOR_EMAIL"
    )

    # ── Derived helpers ───────────────────────────────────────────────
    def provider_for(self, role: Role) -> Provider:
        """Resolve the effective provider for a role (per-role override wins)."""
        override = getattr(self, f"provider_{role}")
        return override or self.provider

    def model_for(self, role: Role) -> str:
        """Resolve the model id for a role under its effective provider."""
        if self.provider_for(role) == "anthropic":
            return getattr(self, f"anthropic_model_{role}")
        return getattr(self, f"model_{role}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
