from __future__ import annotations

from functools import lru_cache

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from agent_trader.core.config import Settings, get_settings


class AgentModelRegistry:
    """统一管理 Agent 到模型实例的映射与创建。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def get_model_name(self, agent_name: str) -> str:
        normalized_name = agent_name.strip()
        if not normalized_name:
            raise ValueError("agent_name must not be empty")
        return self._settings.agent_models.model_map.get(
            normalized_name, self._settings.agent_models.default_model
        )

    def get_chat_model(self, agent_name: str) -> BaseChatModel:
        openai = self._settings.openai
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY is required to initialize agent models")

        return init_chat_model(
            model=self.get_model_name(agent_name),
            model_provider="openai",
            api_key=openai.api_key,
            base_url=openai.base_url,
            timeout=openai.timeout_seconds,
            temperature=openai.temperature,
        )


@lru_cache(maxsize=1)
def get_agent_model_registry() -> AgentModelRegistry:
    return AgentModelRegistry()
