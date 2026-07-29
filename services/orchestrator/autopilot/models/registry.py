"""Role → chat model factory.

This is the one place that knows about concrete providers. Every agent asks for
a *role* ("coder" / "planner" / "router") and gets back a LangChain
``BaseChatModel``; nothing downstream cares whether that is Ollama or Anthropic.
Swapping local↔cloud is a config change, never a code change.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from autopilot.config import Role, Settings, get_settings

# Cache one client per (provider, model, temperature) so we don't rebuild a
# client on every graph node.
_CACHE: dict[tuple, BaseChatModel] = {}


def _build(provider: str, model: str, temperature: float, settings: Settings) -> BaseChatModel:
    if provider == "ollama":
        # Imported lazily so unit tests that only exercise routing don't need
        # the provider packages installed.
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model,
            base_url=settings.ollama_host,
            temperature=temperature,
            num_ctx=32768,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not settings.anthropic_api_key:
            raise RuntimeError(
                "AUTOPILOT_PROVIDER resolves to 'anthropic' but ANTHROPIC_API_KEY is unset."
            )
        return ChatAnthropic(
            model=model,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
            max_tokens=8192,
        )

    raise ValueError(f"unknown provider: {provider!r}")


def get_model(
    role: Role,
    *,
    temperature: float = 0.2,
    settings: Settings | None = None,
) -> BaseChatModel:
    """Return the chat model for ``role`` under the currently-configured provider."""
    settings = settings or get_settings()
    provider = settings.provider_for(role)
    model = settings.model_for(role)
    key = (provider, model, temperature)
    if key not in _CACHE:
        _CACHE[key] = _build(provider, model, temperature, settings)
    return _CACHE[key]


def reset_cache() -> None:
    """Drop cached clients (used by tests that flip provider mid-process)."""
    _CACHE.clear()
