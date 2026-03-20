from __future__ import annotations

import pytest

import agent_trader.agents.models as agent_models_module
from agent_trader.agents.models import AgentModelRegistry
from agent_trader.core.config import Settings


def test_agent_model_registry_returns_mapped_model_name() -> None:
    settings = Settings(
        openai_api_key="test-key",
        agent_default_model="gpt-4.1-mini",
        agent_model_map={"news_preprocess": "gpt-4.1"},
    )
    registry = AgentModelRegistry(settings=settings)

    assert registry.get_model_name("news_preprocess") == "gpt-4.1"
    assert registry.get_model_name("other_agent") == "gpt-4.1-mini"


def test_agent_model_registry_builds_chat_model(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        openai_api_key="test-key",
        agent_default_model="gpt-4.1-mini",
        agent_model_map={"news_preprocess": "gpt-4.1"},
        openai_temperature=0.2,
        openai_timeout_seconds=45,
    )
    registry = AgentModelRegistry(settings=settings)

    captured: dict[str, object] = {}

    class _FakeModel:
        pass

    def _fake_init_chat_model(model: str | None = None, **kwargs: object) -> _FakeModel:
        captured["model"] = model
        captured.update(kwargs)
        return _FakeModel()

    monkeypatch.setattr(agent_models_module, "init_chat_model", _fake_init_chat_model)

    model = registry.get_chat_model("news_preprocess")

    assert isinstance(model, _FakeModel)
    assert captured["model"] == "gpt-4.1"
    assert captured["model_provider"] == "openai"
    assert captured["api_key"] == "test-key"
    assert captured["temperature"] == 0.2
    assert captured["timeout"] == 45


def test_agent_model_registry_requires_openai_api_key() -> None:
    settings = Settings(openai_api_key="")
    registry = AgentModelRegistry(settings=settings)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        registry.get_chat_model("news_preprocess")
