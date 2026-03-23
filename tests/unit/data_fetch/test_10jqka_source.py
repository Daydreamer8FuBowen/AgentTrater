from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from agent_trader.data_fetch.sources import _10jqka


class _DummyRow(dict[str, Any]):
    def to_dict(self) -> dict[str, Any]:
        return dict(self)


class _DummyDataFrame:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows
        self.empty = not rows

    def iterrows(self):  # pragma: no cover - simple helper
        for idx, row in enumerate(self._rows):
            yield idx, _DummyRow(row)


class _DummyProClient:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows
        self.kwargs: dict[str, Any] | None = None

    def news(self, **kwargs: Any) -> _DummyDataFrame:
        self.kwargs = kwargs
        return _DummyDataFrame(self._rows)


def test_fetch_news_filters_keywords_symbol_and_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {
            "datetime": "2026-03-23 09:00:00",
            "title": "银行板块走强",
            "content": "000001.SZ 在银行板块中领涨",
            "channels": "000001.SZ;bank",
        },
        {
            "datetime": "2026-03-23 09:00:00",
            "title": "银行板块走强",
            "content": "重复记录",
            "channels": "000001.SZ",
        },
        {
            "datetime": "2026-03-23 09:30:00",
            "title": "芯片概念震荡",
            "content": "芯片股分化",
            "channels": "688001.SH",
        },
    ]

    created_clients: list[_DummyProClient] = []

    def fake_pro_api(token: str) -> _DummyProClient:
        assert token == "token"
        client = _DummyProClient(rows)
        created_clients.append(client)
        return client

    monkeypatch.setenv("TUSHARE_TOKEN", "token")
    monkeypatch.setattr(_10jqka.ts, "pro_api", fake_pro_api)

    start_time = datetime(2026, 3, 22, 8, 0, 0)
    end_time = datetime(2026, 3, 23, 8, 0, 0)

    results = _10jqka.fetch_news(
        query="银行, 芯片",
        symbol="000001.SZ",
        limit=1,
        start_time=start_time,
        end_time=end_time,
    )

    assert len(results) == 1
    assert results[0]["title"] == "银行板块走强"
    assert created_clients[0].kwargs == {
        "src": "10jqka",
        "start_date": "20260322 08:00:00",
        "end_date": "20260323 08:00:00",
    }


def test_fetch_news_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    with pytest.raises(ValueError):
        _10jqka.fetch_news()


def test_fetch_news_no_call_when_limit_non_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def fake_pro_api(token: str) -> _DummyProClient:  # pragma: no cover - should not be called
        nonlocal called
        called = True
        return _DummyProClient([])

    monkeypatch.setattr(_10jqka.ts, "pro_api", fake_pro_api)
    assert _10jqka.fetch_news(limit=0) == []
    assert called is False
