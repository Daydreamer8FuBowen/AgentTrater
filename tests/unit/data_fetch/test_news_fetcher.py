from __future__ import annotations

from datetime import datetime

from agent_trader.agents.news_preprocess_agent import NewsPreprocessAgent, NewsPreprocessOutput
from agent_trader.data_fetch import NewsFetcher


class _FakeCompiledAgent:
    def __init__(self, payload: NewsPreprocessOutput) -> None:
        self._payload = payload

    def invoke(self, input: object) -> dict[str, NewsPreprocessOutput]:
        del input
        return {"structured_response": self._payload}


class _FakeRegistry:
    def get_chat_model(self, agent_name: str) -> object:
        assert agent_name == "news_preprocess"
        return object()


def test_news_fetcher_returns_cleaned_merged_items() -> None:
    fetcher = NewsFetcher()
    fetcher.register_source(
        "eastmoney",
        lambda **_: [
            {
                "title": "000001.SZ 银行板块走强",
                "content": "银行板块走强，000001.SZ 盘中拉升。",
                "url": "https://example.com/a",
                "published_at": "2026-03-20 09:30:00",
            }
        ],
    )
    fetcher.register_source(
        "sina",
        lambda **_: [
            {
                "headline": "机器人概念再度活跃",
                "summary": "机器人与 AI 概念联动上涨。",
                "link": "https://example.com/b",
            }
        ],
    )

    items = fetcher.fetch_all(query="市场",verbose=True)
    assert len(items) == 2
    assert items[0].source == "eastmoney"
    assert items[1].source == "sina"
    assert any(tag == "robotics" for tag in items[1].concept_tags)


def test_news_preprocess_agent_returns_structured_item(monkeypatch) -> None:
    compiled_agent = _FakeCompiledAgent(
        NewsPreprocessOutput(
            title="000001.SZ 银行板块走强",
            content="银行板块走强，000001.SZ 盘中拉升。",
            summary="银行板块异动，龙头股走强",
            published_at=datetime(2026, 3, 20, 9, 30, 0),
            market="cn_a",
            industry_tags=["bank"],
            stock_tags=["000001.SZ"],
            credibility=0.88,
        )
    )
    monkeypatch.setattr(
        "agent_trader.agents.news_preprocess_agent.create_agent",
        lambda **_: compiled_agent,
    )
    agent = NewsPreprocessAgent(agent_name="news_preprocess", model_registry=_FakeRegistry())

    item = agent.clean(
        source="eastmoney",
        payload={
            "title": "000001.SZ 银行板块走强",
            "content": "银行板块走强，000001.SZ 盘中拉升。",
            "published_at": datetime(2026, 3, 20, 9, 30, 0),
        },
    )

    assert item.summary == "银行板块异动，龙头股走强"
    assert item.market == "cn_a"
    assert item.credibility == 0.88
    assert "bank" in item.industry_tags
    assert "000001.SZ" in item.stock_tags
