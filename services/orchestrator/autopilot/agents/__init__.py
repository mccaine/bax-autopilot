"""Agents — one node function per role in the graph.

Each ``*_node(state) -> dict`` reads ``RunState``, does its job (calling the LLM
via the role-based registry and the tools), and returns a partial state update
that LangGraph merges in.
"""

from autopilot.agents.architect import architect_node
from autopilot.agents.coder import coder_worker_node
from autopilot.agents.deployer import deploy_node
from autopilot.agents.fixer import fix_node
from autopilot.agents.integrator import integrate_node
from autopilot.agents.reviewer import review_node
from autopilot.agents.scaffolder import scaffold_node
from autopilot.agents.spec import spec_node
from autopilot.agents.tester import test_node

__all__ = [
    "spec_node",
    "architect_node",
    "scaffold_node",
    "coder_worker_node",
    "test_node",
    "review_node",
    "fix_node",
    "deploy_node",
    "integrate_node",
]
