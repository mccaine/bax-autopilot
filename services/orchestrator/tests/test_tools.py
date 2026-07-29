import pytest

from autopilot.tools.fs import Workspace, WorkspaceError
from autopilot.tools.shell import DEFAULT_ALLOWLIST, SandboxError, _check_allowed


def test_workspace_write_read_roundtrip(tmp_path):
    ws = Workspace(tmp_path / "app")
    ws.write("src/index.ts", "export const x = 1;\n")
    assert ws.read("src/index.ts").startswith("export const x")
    assert "src/index.ts" in ws.tree()


def test_workspace_rejects_escape(tmp_path):
    ws = Workspace(tmp_path / "app")
    with pytest.raises(WorkspaceError):
        ws.resolve("../../etc/passwd")
    with pytest.raises(WorkspaceError):
        ws.write("../escape.txt", "nope")


def test_workspace_edit_unique(tmp_path):
    ws = Workspace(tmp_path / "app")
    ws.write("a.txt", "hello world hello")
    with pytest.raises(WorkspaceError):
        ws.edit("a.txt", "hello", "hi")  # not unique
    ws.edit("a.txt", "world", "there")
    assert ws.read("a.txt") == "hello there hello"


def test_shell_allowlist_blocks_unknown():
    with pytest.raises(SandboxError):
        _check_allowed("rm -rf /", DEFAULT_ALLOWLIST)
    with pytest.raises(SandboxError):
        _check_allowed("curl http://evil", DEFAULT_ALLOWLIST)


def test_shell_allowlist_permits_known():
    # Should not raise for allowed executables.
    _check_allowed("npm install", DEFAULT_ALLOWLIST)
    _check_allowed("node --test", DEFAULT_ALLOWLIST)
