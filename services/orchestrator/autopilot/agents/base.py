"""Shared helpers for agent nodes: LLM calls, lenient JSON parsing, journaling."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from autopilot.config import Role, get_settings
from autopilot.models import get_model
from autopilot.tools.fs import Workspace

_PROMPTS = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str) -> str:
    path = _PROMPTS / f"{name}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def workspace_for(state: dict) -> Workspace:
    return Workspace(Path(state["workspace"]))


def call_llm(role: Role, system: str, user: str, *, temperature: float = 0.2) -> str:
    """One-shot chat call. Returns the assistant text."""
    model = get_model(role, temperature=temperature)
    resp = model.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return resp.content if isinstance(resp.content, str) else str(resp.content)


_JSON_RE = re.compile(r"\{.*\}|\[.*\]", re.DOTALL)


def parse_json(text: str, *, default: Any = None) -> Any:
    """Extract the first JSON object/array from a model response.

    Local models often wrap JSON in prose or ```json fences; be forgiving.
    """
    text = text.strip()
    # Strip code fences.
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _JSON_RE.search(text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return default


def journal(msg: str) -> dict:
    """Return a partial state update appending one journal line."""
    return {"journal": [msg]}


def budgets_exhausted(state: dict) -> str | None:
    """Return a reason string if any hard budget is blown, else None."""
    s = get_settings()
    if state.get("steps", 0) >= s.step_budget:
        return f"step budget exhausted ({s.step_budget})"
    if s.token_budget and state.get("tokens", 0) >= s.token_budget:
        return f"token budget exhausted ({s.token_budget})"
    return None
