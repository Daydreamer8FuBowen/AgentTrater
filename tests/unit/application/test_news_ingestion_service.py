from __future__ import annotations

from datetime import datetime

import pytest

from agent_trader.application.services.news_ingestion_service import NewsIngestionService
from agent_trader.agents.news_preprocess_agent import NewsPreprocessAgent, NewsPreprocessOutput
from agent_trader.data_fetch import NewsFetcher
from tests.support.in_memory_uow import InMemoryUnitOfWork


class _FakeCompiledAgent:
    def invoke(self, input: object) -> dict[str, NewsPreprocessOutput]:
        del input
        return {
            "structured_response": NewsPreprocessOutput(
                title="000001.SZ 银行板块走强",
                content="银行板块走强，000001.SZ 盘中拉升。",
                summary="银行板块走强，000001.SZ 盘中拉升。",
                published_at=datetime(2026, 3, 20, 9, 30, 0),
                url="https://example.com/a",
                market="cn_a",
                industry_tags=["bank"],
                stock_tags=["000001.SZ"],
                tags=["bank", "000001.SZ"],
                credibility=0.85,
            )
        }


class _FakeRegistry:
    def get_chat_model(self, agent_name: str) -> object:
        assert agent_name == "news_preprocess"
        return object()


@pytest.mark.asyncio
async def test_news_ingestion_service_persists_non_duplicate_news(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "agent_trader.agents.news_preprocess_agent.get_agent_model_registry",
        lambda: _FakeRegistry(),
    )
    monkeypatch.setattr(
        "agent_trader.agents.news_preprocess_agent.create_agent",
        lambda **_: _FakeCompiledAgent(),
    )

    fetcher = NewsFetcher(cleaner=NewsPreprocessAgent())
    fetcher.register_source(
        "eastmoney",
        lambda **_: [
            {
                "title": "000001.SZ 银行板块走强",
                "content": "银行板块走强，000001.SZ 盘中拉升。",
                "url": "https://example.com/a",
                "published_at": "2026-03-20 09:30:00",
            },
            {
                "title": "000001.SZ 银行板块走强",
                "content": "银行板块走强，000001.SZ 盘中拉升。",
                "url": "https://example.com/a",
                "published_at": "2026-03-20 09:30:00",
            },
        ],
    )
    unit_of_work = InMemoryUnitOfWork()
    service = NewsIngestionService(news_fetcher=fetcher, unit_of_work=unit_of_work)

    result = await service.ingest(query="银行")

    assert result.total_fetched == 2
    assert result.inserted_count == 1
    assert result.duplicate_count == 1
    assert len(unit_of_work.store.news_items) == 1
    assert unit_of_work.store.news_items[0].source == "eastmoney"