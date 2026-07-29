from autopilot.config import Settings


def test_provider_and_model_resolution_defaults():
    s = Settings(provider="ollama")
    assert s.provider_for("coder") == "ollama"
    assert s.model_for("coder") == s.model_coder
    assert s.model_for("planner") == s.model_planner


def test_per_role_provider_override_wins():
    s = Settings(provider="ollama", provider_coder="anthropic")
    assert s.provider_for("coder") == "anthropic"
    assert s.model_for("coder") == s.anthropic_model_coder
    # other roles still local
    assert s.provider_for("planner") == "ollama"
    assert s.model_for("planner") == s.model_planner


def test_global_anthropic_switch():
    s = Settings(provider="anthropic")
    assert s.provider_for("router") == "anthropic"
    assert s.model_for("router") == s.anthropic_model_router
