from autopilot import graph as graph_mod
from autopilot.agents import base as base_mod
from autopilot.config import Settings


def _patch_settings(monkeypatch, **kw):
    s = Settings(**kw)
    monkeypatch.setattr(graph_mod, "get_settings", lambda: s)
    monkeypatch.setattr(base_mod, "get_settings", lambda: s)
    return s


def test_route_after_test_pass_goes_to_review(monkeypatch):
    _patch_settings(monkeypatch, max_fix_iters=3, step_budget=100)
    assert graph_mod._route_after_test({"test_ok": True, "fix_iters": 0, "steps": 1}) == "review"


def test_route_after_test_fail_goes_to_fix_then_blocked(monkeypatch):
    _patch_settings(monkeypatch, max_fix_iters=2, step_budget=100)
    assert graph_mod._route_after_test({"test_ok": False, "fix_iters": 0, "steps": 1}) == "fix"
    # cap reached → blocked
    assert graph_mod._route_after_test({"test_ok": False, "fix_iters": 2, "steps": 1}) == "blocked"


def test_step_budget_forces_blocked(monkeypatch):
    _patch_settings(monkeypatch, max_fix_iters=99, step_budget=5)
    assert graph_mod._route_after_test({"test_ok": False, "fix_iters": 0, "steps": 5}) == "blocked"


def test_route_after_review(monkeypatch):
    _patch_settings(monkeypatch, max_fix_iters=3, step_budget=100)
    assert graph_mod._route_after_review({"review_ok": True, "fix_iters": 0, "steps": 1}) == "deploy"
    assert graph_mod._route_after_review({"review_ok": False, "fix_iters": 0, "steps": 1}) == "fix"


def test_blocked_node_sets_status(monkeypatch):
    _patch_settings(monkeypatch, step_budget=1)
    out = graph_mod._blocked_node({"steps": 5})
    assert out["status"] == "blocked"
    assert out["journal"]
