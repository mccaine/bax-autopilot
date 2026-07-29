from autopilot import config
from autopilot.models import registry


class _Fake:
    def __init__(self, provider, model):
        self.provider = provider
        self.model = model


def test_get_model_routes_and_caches(monkeypatch):
    calls = []

    def fake_build(provider, model, temperature, settings):
        calls.append((provider, model))
        return _Fake(provider, model)

    monkeypatch.setattr(registry, "_build", fake_build)
    registry.reset_cache()

    s = config.Settings(provider="ollama")
    m1 = registry.get_model("coder", settings=s)
    m2 = registry.get_model("coder", settings=s)  # cached — no second build
    assert m1 is m2
    assert m1.provider == "ollama"
    assert m1.model == s.model_coder
    assert len(calls) == 1


def test_get_model_switches_provider(monkeypatch):
    monkeypatch.setattr(registry, "_build", lambda p, m, t, s: _Fake(p, m))
    registry.reset_cache()

    local = registry.get_model("planner", settings=config.Settings(provider="ollama"))
    cloud = registry.get_model("planner", settings=config.Settings(provider="anthropic"))
    assert local.provider == "ollama"
    assert cloud.provider == "anthropic"
    assert cloud.model.startswith("claude-")
