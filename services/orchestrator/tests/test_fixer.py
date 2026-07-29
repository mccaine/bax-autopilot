"""Fixer fast rebuild-only self-check: on a build failure it re-patches against
the build error before handing back to the full test run."""

from types import SimpleNamespace as SN

from autopilot.agents import base as base_mod
from autopilot.agents import fixer as fixer_mod
from autopilot.config import Settings
from autopilot.tools import compose as compose_mod


def test_fixer_rebuilds_and_repatches(monkeypatch, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    settings = Settings(fix_inner_retries=2)
    monkeypatch.setattr(fixer_mod, "get_settings", lambda: settings)

    calls = {"n": 0}

    class Model:
        def invoke(self, _messages):
            calls["n"] += 1
            return SN(content='{"services/api/src/routes/x.ts": "export default (a, p) => {};\\n"}')

    monkeypatch.setattr(base_mod, "get_model", lambda *a, **k: Model())

    # First build fails (triggers one re-patch), second build passes.
    builds = [SN(ok=False, summary=lambda **k: "build err"), SN(ok=True, summary=lambda **k: "ok")]
    monkeypatch.setattr(compose_mod, "build", lambda d: builds.pop(0))

    state = {"workspace": str(ws), "test_report": "boom", "fix_iters": 0, "steps": 0}
    out = fixer_mod.fix_node(state)

    assert out["fix_iters"] == 1
    assert out["phase"] == "test"
    # initial patch + one rebuild-driven re-patch == 2 model calls
    assert calls["n"] == 2
    assert (ws / "services" / "api" / "src" / "routes" / "x.ts").exists()


def test_fixer_skips_selfcheck_without_docker(monkeypatch, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    settings = Settings(fix_inner_retries=2)
    monkeypatch.setattr(fixer_mod, "get_settings", lambda: settings)

    calls = {"n": 0}

    class Model:
        def invoke(self, _messages):
            calls["n"] += 1
            return SN(content='{"a.ts": "1"}')

    monkeypatch.setattr(base_mod, "get_model", lambda *a, **k: Model())

    def boom(_d):
        raise RuntimeError("no docker")

    monkeypatch.setattr(compose_mod, "build", boom)

    out = fixer_mod.fix_node({"workspace": str(ws), "test_report": "x", "fix_iters": 0, "steps": 0})
    assert out["fix_iters"] == 1
    # only the initial patch — self-check skipped cleanly when build can't run
    assert calls["n"] == 1
