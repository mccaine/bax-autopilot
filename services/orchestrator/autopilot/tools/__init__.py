"""Agent tools — the hands. Filesystem, sandboxed shell/compose, git, terraform.

Everything here is workspace-scoped and side-effecting; agents call these rather
than touching the host directly.
"""
