from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from langchain.agents import create_agent
from pydantic import BaseModel, Field, field_validator

from agent_trader.agents.models import AgentModelRegistry, get_agent_model_registry
from agent_trader.data_fetch.cleaning import build_news_dedupe_key, parse_published_at
from agent_trader.data_fetch.models import CleanedNewsItem


class NewsPreprocessOutput(BaseModel):
    """新闻预处理 Agent 的结构化输出。"""

    title: str = Field(min_length=1)
    content: str = ""
    summary: str = ""
    published_at: datetime | str | None = None
    url: str | None = None
    market: str = "unknown"
    industry_tags: list[str] = Field(default_factory=list)
    concept_tags: list[str] = Field(default_factory=list)
    stock_tags: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    credibility: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("title", "content", "summary", "market", mode="before")
    @classmethod
    def _normalize_text(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("url", mode="before")
    @classmethod
    def _normalize_url(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("industry_tags", "concept_tags", "stock_tags", "tags", mode="before")
    @classmethod
    def _normalize_tags(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            items = [part.strip() for part in value.replace("，", ",").split(",")]
        elif isinstance(value, list):
            items = [str(part).strip() for part in value]
        else:
            items = [str(value).strip()]

        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            if not item:
                continue
            lowered = item.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(item)
        return deduped


class NewsPreprocessAgent:
    """基于 LangChain `create_agent` 的新闻预处理 Agent。

    该 Agent 按名称从统一 model registry 获取模型，并直接返回结构化清洗结果。
    """

    _SYSTEM_PROMPT = (
        "你是新闻预处理 Agent。"
        "请从输入新闻中提取结构化字段，并严格遵守给定 schema。"
        "不要编造来源中不存在的事实；缺失字段使用空字符串、空数组或 null。"
        "market 必须使用简短标识，例如 cn_a、hk、us、crypto、unknown。"
        "tags 仅保留对后续检索和聚类有价值的主题标签。"
    )

    def __init__(
        self,
        agent_name: str = "news_preprocess",
        model_registry: AgentModelRegistry | None = None,
    ) -> None:
        self._agent_name = agent_name
        self._model_registry = model_registry or get_agent_model_registry()
        self._agent = create_agent(
            model=self._model_registry.get_chat_model(agent_name),
            tools=[],
            system_prompt=self._SYSTEM_PROMPT,
            response_format=NewsPreprocessOutput,
            name=agent_name,
        )

    def clean(self, *, source: str, payload: dict[str, Any]) -> CleanedNewsItem:
        response = self._agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": self._build_user_message(source=source, payload=payload),
                    }
                ]
            }
        )
        structured = response.get("structured_response")
        if not isinstance(structured, NewsPreprocessOutput):
            raise ValueError(f"agent {self._agent_name} did not return a valid structured_response")

        published_at = parse_published_at(structured.published_at)
        title = structured.title.strip()
        content = structured.content
        summary = structured.summary or (content[:120] if content else title[:120])
        market = structured.market.lower() if structured.market else "unknown"
        url = structured.url

        return CleanedNewsItem(
            title=title,
            content=content,
            summary=summary,
            source=source,
            published_at=published_at,
            url=url,
            market=market,
            industry_tags=structured.industry_tags,
            concept_tags=structured.concept_tags,
            stock_tags=structured.stock_tags,
            tags=structured.tags,
            credibility=structured.credibility,
            raw_payload=dict(payload),
            dedupe_key=build_news_dedupe_key(
                source=source,
                title=title,
                url=url,
                published_at=published_at,
            ),
        )

    def clean_batch(self, *, source: str, payloads: list[dict[str, Any]]) -> list[CleanedNewsItem]:
        return [self.clean(source=source, payload=payload) for payload in payloads]

    def _build_user_message(self, *, source: str, payload: dict[str, Any]) -> str:
        return f"source={source}\npayload={json.dumps(payload, ensure_ascii=False, default=str)}"
