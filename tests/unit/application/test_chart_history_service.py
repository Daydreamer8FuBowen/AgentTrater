from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agent_trader.application.data_access.kline_utils import MAX_KLINE_BARS
from agent_trader.application.services.chart_history_service import (
    ChartHistoryService,
    _build_fetch_chunks,
)
from agent_trader.core.time import market_time_to_utc
from agent_trader.domain.models import BarInterval, ExchangeKind
from agent_trader.ingestion.models import (
    DataCapability,
    DataRouteKey,
    KlineFetchResult,
    KlineRecord,
)


class StubCandleRepository:
    def __init__(self, responses: list[list[dict[str, object]]]) -> None:
        self._responses = list(responses)
        self.queries: list[dict[str, object]] = []
        self.written_batches: list[list[object]] = []

    async def query_history(self, **kwargs):
        self.queries.append(kwargs)
        if self._responses:
            return self._responses.pop(0)
        return []

    async def write_batch(self, candles):
        self.written_batches.append(list(candles))


class StubGateway:
    """可以按次返回不同结果的 gateway stub。"""

    def __init__(self, results: list[KlineFetchResult] | KlineFetchResult) -> None:
        if isinstance(results, KlineFetchResult):
            results = [results]
        self._results = list(results)
        self._default = self._results[-1]
        self.queries = []

    async def fetch_klines(self, query):
        self.queries.append(query)
        if self._results:
            return self._results.pop(0)
        return self._default


def _row(bar_time: datetime, close: float) -> dict[str, object]:
    return {
        "symbol": "000066.SZ",
        "interval": "1d",
        "bar_time": bar_time,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": 10.0,
    }


def _daily_bar_time(year: int, month: int, day: int) -> datetime:
    return market_time_to_utc(datetime(year, month, day), "szse")


def _record(bar_time: datetime, close: float) -> KlineRecord:
    return KlineRecord(
        symbol="000066.SZ",
        bar_time=bar_time,
        interval=BarInterval.D1.value,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=10.0,
        amount=100.0,
        change_pct=None,
        turnover_rate=None,
        adjusted=False,
    )


@pytest.mark.asyncio
async def test_get_tv_history_uses_influx_when_data_complete() -> None:
    rows = [
        _row(_daily_bar_time(2025, 3, 26), 1.0),
        _row(_daily_bar_time(2025, 3, 27), 2.0),
        _row(_daily_bar_time(2025, 3, 28), 3.0),
    ]
    repository = StubCandleRepository([rows])
    gateway = StubGateway(
        KlineFetchResult(
            source="baostock",
            route_key=DataRouteKey(
                capability=DataCapability.KLINE,
                market=None,
                interval=BarInterval.D1,
            ),
            payload=[],
        )
    )
    service = ChartHistoryService(repository, gateway)

    result = await service.get_tv_history(
        symbol="000066.SZ",
        resolution="D",
        from_ts=int(datetime(2025, 3, 26, tzinfo=timezone.utc).timestamp()),
        to_ts=int(datetime(2025, 3, 28, tzinfo=timezone.utc).timestamp()),
        countback=3,
    )

    assert result["s"] == "ok"
    assert result["c"] == [1.0, 2.0, 3.0]
    assert gateway.queries == []
    assert repository.written_batches == []


@pytest.mark.asyncio
async def test_get_tv_history_chunks_large_range() -> None:
    """超过 MAX_KLINE_BARS 的请求应拆成多个 gateway 调用写入 InfluxDB。

    使用 2019-01-02 → 2024-01-02 共约 5 年（~1250 个交易日 > MAX_KLINE_BARS=1000），
    强制触发两段拉取。
    """
    chunk1_records = [
        _record(_daily_bar_time(2019, 1, 2), 1.0),
        _record(_daily_bar_time(2019, 1, 3), 2.0),
    ]
    chunk2_records = [
        _record(_daily_bar_time(2023, 6, 1), 3.0),
        _record(_daily_bar_time(2023, 6, 2), 4.0),
    ]
    _route = DataRouteKey(capability=DataCapability.KLINE, market=None, interval=BarInterval.D1)
    gateway = StubGateway(
        [
            KlineFetchResult(source="baostock", route_key=_route, payload=chunk1_records),
            KlineFetchResult(source="baostock", route_key=_route, payload=chunk2_records),
        ]
    )

    hydrated_rows = [
        _row(_daily_bar_time(2019, 1, 2), 1.0),
        _row(_daily_bar_time(2019, 1, 3), 2.0),
        _row(_daily_bar_time(2023, 6, 1), 3.0),
        _row(_daily_bar_time(2023, 6, 2), 4.0),
    ]
    repository = StubCandleRepository([[], hydrated_rows])

    service = ChartHistoryService(repository, gateway)
    result = await service.get_tv_history(
        symbol="000066.SZ",
        resolution="D",
        from_ts=int(datetime(2019, 1, 2, tzinfo=timezone.utc).timestamp()),
        to_ts=int(datetime(2024, 1, 2, tzinfo=timezone.utc).timestamp()),
        countback=4,
    )

    assert result["s"] == "ok"
    assert len(gateway.queries) == 2
    assert len(repository.written_batches) == 1
    assert len(repository.written_batches[0]) == 4


def test_build_fetch_chunks_single_chunk() -> None:
    """预估数量 <= MAX_KLINE_BARS 时应只产生一个子段。"""
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = datetime(2025, 3, 1, tzinfo=timezone.utc)
    chunks = _build_fetch_chunks(start, end, BarInterval.D1, ExchangeKind.SZSE, 500)
    assert len(chunks) == 1
    assert chunks[0] == (start, end)


def test_build_fetch_chunks_splits_correctly() -> None:
    """预估数量超过上限时应切割，各段首尾相接且覆盖完整区间。"""
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, tzinfo=timezone.utc)
    total_expected = MAX_KLINE_BARS * 3  # 强制 3 段
    chunks = _build_fetch_chunks(start, end, BarInterval.D1, ExchangeKind.SZSE, total_expected)
    assert len(chunks) == 3
    assert chunks[0][0] == start
    assert chunks[-1][1] == end
    # 相邻子段首尾相接
    for i in range(len(chunks) - 1):
        assert chunks[i][1] == chunks[i + 1][0]


def test_build_fetch_chunks_aligns_to_minute_precision() -> None:
    start = datetime(2025, 1, 1, 9, 30, 17, 321000, tzinfo=timezone.utc)
    end = datetime(2025, 1, 3, 15, 0, 59, 999000, tzinfo=timezone.utc)
    chunks = _build_fetch_chunks(start, end, BarInterval.D1, ExchangeKind.SSE, MAX_KLINE_BARS * 2)
    assert len(chunks) == 2
    for chunk_start, chunk_end in chunks:
        assert chunk_start.second == 0
        assert chunk_start.microsecond == 0
        assert chunk_end.second == 0
        assert chunk_end.microsecond == 0


@pytest.mark.asyncio
async def test_get_tv_history_backfills_and_persists_missing_data() -> None:
    initial_rows = [
        _row(_daily_bar_time(2025, 3, 26), 1.0),
    ]
    hydrated_rows = [
        _row(_daily_bar_time(2025, 3, 26), 1.0),
        _row(_daily_bar_time(2025, 3, 27), 2.0),
        _row(_daily_bar_time(2025, 3, 28), 3.0),
    ]
    repository = StubCandleRepository([initial_rows, hydrated_rows])
    gateway = StubGateway(
        KlineFetchResult(
            source="baostock",
            route_key=DataRouteKey(
                capability=DataCapability.KLINE,
                market=None,
                interval=BarInterval.D1,
            ),
            payload=[
                _record(_daily_bar_time(2025, 3, 26), 1.0),
                _record(_daily_bar_time(2025, 3, 27), 2.0),
                _record(_daily_bar_time(2025, 3, 28), 3.0),
            ],
        )
    )
    service = ChartHistoryService(repository, gateway)

    result = await service.get_tv_history(
        symbol="000066.SZ",
        resolution="D",
        from_ts=int(datetime(2025, 3, 26, tzinfo=timezone.utc).timestamp()),
        to_ts=int(datetime(2025, 3, 28, tzinfo=timezone.utc).timestamp()),
        countback=3,
    )

    assert result["s"] == "ok"
    assert result["c"] == [1.0, 2.0, 3.0]
    assert len(gateway.queries) == 1
    assert len(repository.written_batches) == 1
    assert len(repository.written_batches[0]) == 3
