from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from agent_trader.application.jobs import kline_sync as kline_sync_module
from agent_trader.application.jobs.kline_sync import (
    KlineSyncService,
    TierCollectionService,
    TieredSymbols,
)
from agent_trader.core.config import KlineSyncConfig
from agent_trader.core.time import market_time_to_utc, to_market_time
from agent_trader.domain.models import BarInterval, ExchangeKind
from agent_trader.ingestion.models import (
    DataCapability,
    DataRouteKey,
    KlineFetchResult,
    KlineRecord,
)
from support.in_memory_uow import InMemoryEventStore, InMemoryUnitOfWork


class _StubGateway:
    def __init__(self, result: KlineFetchResult, *, should_raise: bool = False) -> None:
        self._result = result
        self._should_raise = should_raise
        self.calls: list[object] = []

    async def fetch_klines(self, query: object) -> KlineFetchResult:
        self.calls.append(query)
        if self._should_raise:
            raise RuntimeError("mock fetch failure")
        return self._result


class _InMemoryCandleRepository:
    def __init__(self) -> None:
        self.batches: list[list[object]] = []

    async def write(self, candle: object) -> None:
        self.batches.append([candle])

    async def write_batch(self, candles: list[object]) -> None:
        self.batches.append(candles)


class _StubTierService:
    def __init__(self, tiers: TieredSymbols) -> None:
        self._tiers = tiers

    async def collect(self, market: str) -> TieredSymbols:  # noqa: ARG002
        return self._tiers


@pytest.mark.asyncio
async def test_tier_collection_service_split_abc() -> None:
    store = InMemoryEventStore()
    store.positions = [
        SimpleNamespace(symbol="600000.SH"),
        SimpleNamespace(symbol="600051.SH"),
        SimpleNamespace(symbol="000001.SZ"),
    ]
    store.candidates = [
        SimpleNamespace(symbol="600000.SH"),
        SimpleNamespace(symbol="600010.SH"),
        SimpleNamespace(symbol="600052.SH"),
        SimpleNamespace(symbol="600053.SH"),
        SimpleNamespace(symbol="000002.SZ"),
    ]
    store.basic_info_items = {
            "600000.SH": SimpleNamespace(
                symbol="600000.SH", market=ExchangeKind.SSE, status="1", security_type="stock", name="浦发银行"
            ),
            "600010.SH": SimpleNamespace(
                symbol="600010.SH", market=ExchangeKind.SSE, status="1", security_type="stock", name="包钢股份"
            ),
            "600050.SH": SimpleNamespace(
                symbol="600050.SH", market=ExchangeKind.SSE, status="1", security_type="stock", name="中国联通"
            ),
            "600051.SH": SimpleNamespace(
                symbol="600051.SH", market=ExchangeKind.SSE, status="0", security_type="stock", name="停牌示例"
            ),
            "600052.SH": SimpleNamespace(
                symbol="600052.SH", market=ExchangeKind.SSE, status="1", security_type="fund", name="示例基金"
            ),
            "600053.SH": SimpleNamespace(
                symbol="600053.SH", market=ExchangeKind.SSE, status="1", security_type="stock", name="ST示例"
            ),
            "000001.SZ": SimpleNamespace(
                symbol="000001.SZ", market=ExchangeKind.SZSE, status="1", security_type="stock", name="平安银行"
            ),
            "000002.SZ": SimpleNamespace(
                symbol="000002.SZ", market=ExchangeKind.SZSE, status="1", security_type="stock", name="万科A"
            ),
        }

    service = TierCollectionService(uow_factory=lambda: InMemoryUnitOfWork(store=store))
    tiers = await service.collect(ExchangeKind.SSE)

    assert tiers.market == ExchangeKind.SSE
    assert tiers.positions == ("600000.SH",)
    assert tiers.candidates == ("600010.SH",)
    assert tiers.others == ("600050.SH",)


@pytest.mark.asyncio
async def test_sync_realtime_m5_positions_uses_latest_completed_bar() -> None:
    store = InMemoryEventStore()
    store.basic_info_items["600000.SH"] = SimpleNamespace(
        symbol="600000.SH",
        market=ExchangeKind.SSE,
        status="1",
        security_type="stock",
        name="浦发银行",
        primary_source="baostock",
        source_trace=["tushare"],
    )
    uow = InMemoryUnitOfWork(store=store)
    gateway = _StubGateway(
        KlineFetchResult(
            source="stub",
            route_key=DataRouteKey(
                capability=DataCapability.KLINE,
                market=ExchangeKind.SSE,
                interval=BarInterval.M5,
            ),
            payload=[
                KlineRecord(
                    symbol="600000.SH",
                    bar_time=market_time_to_utc(datetime(2026, 3, 23, 9, 30, 0), ExchangeKind.SSE),
                    interval="5m",
                    open=10.0,
                    high=10.5,
                    low=9.9,
                    close=10.2,
                    volume=1000.0,
                    amount=10000.0,
                    change_pct=None,
                    turnover_rate=None,
                    adjusted=True,
                ),
                KlineRecord(
                    symbol="600000.SH",
                    bar_time=market_time_to_utc(datetime(2026, 3, 23, 9, 35, 0), ExchangeKind.SSE),
                    interval="5m",
                    open=10.2,
                    high=10.6,
                    low=10.1,
                    close=10.4,
                    volume=800.0,
                    amount=9000.0,
                    change_pct=None,
                    turnover_rate=None,
                    adjusted=True,
                ),
            ],
        )
    )
    candles = _InMemoryCandleRepository()
    tier_service = _StubTierService(
        TieredSymbols(market=ExchangeKind.SSE, positions=("600000.SH",), candidates=(), others=())
    )

    service = KlineSyncService(
        gateway=gateway,
        candle_repository=candles,
        uow_factory=lambda: uow,
        tier_collection_service=tier_service,
        config=KlineSyncConfig(
            enabled_markets=[ExchangeKind.SSE],
            d1_window_days=730,
            m5_window_days=60,
            realtime_m5_interval_seconds=60,
            d1_sync_hour=17,
            backfill_batch_symbols=20,
            m5_backfill_chunk_days=20,
        ),
        now_provider=lambda: datetime(2026, 3, 23, 1, 43, 0, tzinfo=timezone.utc),
    )

    summary = await service.sync_realtime_m5_positions(ExchangeKind.SSE)

    assert summary["synced"] == 1
    assert summary["failed"] == 0
    query = gateway.calls[0]
    assert query.start_time == market_time_to_utc(datetime(2026, 3, 23, 9, 30, 0), ExchangeKind.SSE)
    assert query.end_time == market_time_to_utc(datetime(2026, 3, 23, 9, 35, 0), ExchangeKind.SSE)
    assert query.extra["available_sources"] == ["baostock", "tushare"]
    assert len(candles.batches) == 1
    assert store.kline_sync_states["600000.SH:sse:5m"]["last_bar_time"] == market_time_to_utc(
        datetime(2026, 3, 23, 9, 35, 0), ExchangeKind.SSE
    )


@pytest.mark.asyncio
async def test_sync_realtime_m5_positions_skips_before_first_completed_bar() -> None:
    store = InMemoryEventStore()
    uow = InMemoryUnitOfWork(store=store)
    gateway = _StubGateway(
        KlineFetchResult(
            source="stub",
            route_key=DataRouteKey(
                capability=DataCapability.KLINE,
                market=ExchangeKind.SSE,
                interval=BarInterval.M5,
            ),
            payload=[],
        )
    )
    service = KlineSyncService(
        gateway=gateway,
        candle_repository=_InMemoryCandleRepository(),
        uow_factory=lambda: uow,
        tier_collection_service=_StubTierService(
            TieredSymbols(market=ExchangeKind.SSE, positions=("600000.SH",), candidates=(), others=())
        ),
        config=KlineSyncConfig(
            enabled_markets=[ExchangeKind.SSE],
            d1_window_days=730,
            m5_window_days=60,
            realtime_m5_interval_seconds=60,
            d1_sync_hour=17,
            backfill_batch_symbols=20,
            m5_backfill_chunk_days=20,
        ),
        now_provider=lambda: datetime(2026, 3, 23, 1, 31, 0, tzinfo=timezone.utc),
    )

    summary = await service.sync_realtime_m5_positions(ExchangeKind.SSE)

    assert summary["mode"] == "await_bar_close"
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_sync_backfill_m5_uses_state_to_resume() -> None:
    store = InMemoryEventStore()
    store.kline_sync_states["600000.SH:sse:5m"] = {
        "state_id": "600000.SH:sse:5m",
        "symbol": "600000.SH",
        "market": ExchangeKind.SSE,
        "interval": "5m",
        "last_bar_time": market_time_to_utc(datetime(2026, 3, 20, 14, 55, 0), ExchangeKind.SSE),
        "last_fetched_at": None,
        "status": "ok",
    }
    uow = InMemoryUnitOfWork(store=store)
    gateway = _StubGateway(
        KlineFetchResult(
            source="stub",
            route_key=DataRouteKey(
                capability=DataCapability.KLINE,
                market=ExchangeKind.SSE,
                interval=BarInterval.M5,
            ),
            payload=[
                KlineRecord(
                    symbol="600000.SH",
                    bar_time=market_time_to_utc(datetime(2026, 3, 24, 15, 0, 0), ExchangeKind.SSE),
                    interval="5m",
                    open=10.0,
                    high=10.2,
                    low=9.8,
                    close=10.1,
                    volume=100.0,
                    amount=1000.0,
                    change_pct=None,
                    turnover_rate=None,
                    adjusted=True,
                )
            ],
        )
    )
    service = KlineSyncService(
        gateway=gateway,
        candle_repository=_InMemoryCandleRepository(),
        uow_factory=lambda: uow,
        tier_collection_service=_StubTierService(
            TieredSymbols(market=ExchangeKind.SSE, positions=("600000.SH",), candidates=(), others=())
        ),
        config=KlineSyncConfig(
            enabled_markets=[ExchangeKind.SSE],
            d1_window_days=730,
            m5_window_days=60,
            realtime_m5_interval_seconds=60,
            d1_sync_hour=17,
            backfill_batch_symbols=20,
            m5_backfill_chunk_days=20,
        ),
        now_provider=lambda: datetime(2026, 3, 24, 8, 0, 0, tzinfo=timezone.utc),
    )

    summary = await service.sync_backfill_m5_positions_candidates(ExchangeKind.SSE)

    assert summary["synced"] == 1
    query = gateway.calls[0]
    assert query.start_time == market_time_to_utc(datetime(2026, 3, 20, 15, 0, 0), ExchangeKind.SSE)
    assert query.end_time == market_time_to_utc(datetime(2026, 3, 24, 15, 0, 0), ExchangeKind.SSE)


@pytest.mark.asyncio
async def test_sync_market_routes_to_history_outside_trading_hours() -> None:
    store = InMemoryEventStore()
    uow = InMemoryUnitOfWork(store=store)
    gateway = _StubGateway(
        KlineFetchResult(
            source="stub",
            route_key=DataRouteKey(
                capability=DataCapability.KLINE,
                market=ExchangeKind.SSE,
                interval=BarInterval.D1,
            ),
            payload=[
                KlineRecord(
                    symbol="600000.SH",
                    bar_time=market_time_to_utc(datetime(2026, 3, 26, 9, 0, 0), ExchangeKind.SSE),
                    interval="1d",
                    open=10.0,
                    high=10.5,
                    low=9.8,
                    close=10.2,
                    volume=1000.0,
                    amount=10000.0,
                    change_pct=None,
                    turnover_rate=None,
                    adjusted=True,
                )
            ],
        )
    )
    service = KlineSyncService(
        gateway=gateway,
        candle_repository=_InMemoryCandleRepository(),
        uow_factory=lambda: uow,
        tier_collection_service=_StubTierService(
            TieredSymbols(market=ExchangeKind.SSE, positions=("600000.SH",), candidates=(), others=())
        ),
        config=KlineSyncConfig(
            enabled_markets=[ExchangeKind.SSE],
            d1_window_days=730,
            m5_window_days=60,
            realtime_m5_interval_seconds=60,
            d1_sync_hour=17,
            backfill_batch_symbols=20,
            m5_backfill_chunk_days=20,
        ),
        now_provider=lambda: datetime(2026, 3, 26, 8, 0, 0, tzinfo=timezone.utc),
    )

    summary = await service.sync_market(ExchangeKind.SSE)

    assert summary["mode"] == "history"
    assert summary["history"]["1d"]["synced"] == 1


@pytest.mark.asyncio
async def test_d1_history_during_trading_uses_previous_trade_day() -> None:
    store = InMemoryEventStore()
    uow = InMemoryUnitOfWork(store=store)
    gateway = _StubGateway(
        KlineFetchResult(
            source="stub",
            route_key=DataRouteKey(
                capability=DataCapability.KLINE,
                market=ExchangeKind.SSE,
                interval=BarInterval.D1,
            ),
            payload=[
                KlineRecord(
                    symbol="600000.SH",
                    bar_time=market_time_to_utc(datetime(2026, 3, 25, 9, 0, 0), ExchangeKind.SSE),
                    interval="1d",
                    open=10.0,
                    high=10.5,
                    low=9.8,
                    close=10.2,
                    volume=1000.0,
                    amount=10000.0,
                    change_pct=None,
                    turnover_rate=None,
                    adjusted=True,
                )
            ],
        )
    )
    service = KlineSyncService(
        gateway=gateway,
        candle_repository=_InMemoryCandleRepository(),
        uow_factory=lambda: uow,
        tier_collection_service=_StubTierService(
            TieredSymbols(market=ExchangeKind.SSE, positions=("600000.SH",), candidates=(), others=())
        ),
        config=KlineSyncConfig(
            enabled_markets=[ExchangeKind.SSE],
            d1_window_days=730,
            m5_window_days=60,
            realtime_m5_interval_seconds=60,
            d1_sync_hour=17,
            backfill_batch_symbols=20,
            m5_backfill_chunk_days=20,
        ),
        now_provider=lambda: datetime(2026, 3, 26, 2, 0, 0, tzinfo=timezone.utc),
    )

    summary = await service.sync_backfill_d1_all(ExchangeKind.SSE)

    assert summary["synced"] == 1
    assert store.kline_sync_states["600000.SH:sse:1d"]["last_bar_time"] == market_time_to_utc(
        datetime(2026, 3, 25, 9, 0, 0), ExchangeKind.SSE
    )


@pytest.mark.asyncio
async def test_sync_backfill_d1_all_processes_all_symbols_without_batch_selection() -> None:
    store = InMemoryEventStore()
    uow = InMemoryUnitOfWork(store=store)
    gateway = _StubGateway(
        KlineFetchResult(
            source="stub",
            route_key=DataRouteKey(
                capability=DataCapability.KLINE,
                market=ExchangeKind.SSE,
                interval=BarInterval.D1,
            ),
            payload=[
                KlineRecord(
                    symbol="600000.SH",
                    bar_time=market_time_to_utc(datetime(2026, 3, 26, 9, 0, 0), ExchangeKind.SSE),
                    interval="1d",
                    open=10.0,
                    high=10.5,
                    low=9.8,
                    close=10.2,
                    volume=1000.0,
                    amount=10000.0,
                    change_pct=None,
                    turnover_rate=None,
                    adjusted=True,
                )
            ],
        )
    )
    service = KlineSyncService(
        gateway=gateway,
        candle_repository=_InMemoryCandleRepository(),
        uow_factory=lambda: uow,
        tier_collection_service=_StubTierService(
            TieredSymbols(
                market=ExchangeKind.SSE,
                positions=("600000.SH", "600001.SH"),
                candidates=("600002.SH",),
                others=("600003.SH",),
            )
        ),
        config=KlineSyncConfig(
            enabled_markets=[ExchangeKind.SSE],
            d1_window_days=730,
            m5_window_days=60,
            realtime_m5_interval_seconds=60,
            d1_sync_hour=17,
            backfill_batch_symbols=2,
            m5_backfill_chunk_days=20,
        ),
        now_provider=lambda: datetime(2026, 3, 27, 2, 0, 0, tzinfo=timezone.utc),
    )

    summary = await service.sync_backfill_d1_all(ExchangeKind.SSE)

    assert summary["synced"] == 4
    assert len(gateway.calls) == 4


@pytest.mark.asyncio
async def test_sync_backfill_d1_skips_api_when_state_already_latest_by_date() -> None:
    store = InMemoryEventStore()
    store.kline_sync_states["600000.SH:sse:1d"] = {
        "state_id": "600000.SH:sse:1d",
        "symbol": "600000.SH",
        "market": ExchangeKind.SSE,
        "interval": "1d",
        "last_bar_time": market_time_to_utc(datetime(2026, 3, 26, 9, 0, 0), ExchangeKind.SSE),
        "last_fetched_at": datetime(2026, 3, 26, 10, 0, 0, tzinfo=timezone.utc),
        "status": "ok",
    }
    uow = InMemoryUnitOfWork(store=store)
    gateway = _StubGateway(
        KlineFetchResult(
            source="stub",
            route_key=DataRouteKey(
                capability=DataCapability.KLINE,
                market=ExchangeKind.SSE,
                interval=BarInterval.D1,
            ),
            payload=[],
        )
    )
    service = KlineSyncService(
        gateway=gateway,
        candle_repository=_InMemoryCandleRepository(),
        uow_factory=lambda: uow,
        tier_collection_service=_StubTierService(
            TieredSymbols(market=ExchangeKind.SSE, positions=("600000.SH",), candidates=(), others=())
        ),
        config=KlineSyncConfig(
            enabled_markets=[ExchangeKind.SSE],
            d1_window_days=730,
            m5_window_days=60,
            realtime_m5_interval_seconds=60,
            d1_sync_hour=17,
            backfill_batch_symbols=20,
            m5_backfill_chunk_days=20,
        ),
        now_provider=lambda: datetime(2026, 3, 27, 2, 0, 0, tzinfo=timezone.utc),
    )

    summary = await service.sync_backfill_d1_all(ExchangeKind.SSE)

    assert summary["synced"] == 0
    assert summary["skipped"] == 1
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_sync_realtime_fetch_error_is_logged_and_skipped() -> None:
    store = InMemoryEventStore()
    uow = InMemoryUnitOfWork(store=store)
    gateway = _StubGateway(
        KlineFetchResult(
            source="stub",
            route_key=DataRouteKey(
                capability=DataCapability.KLINE,
                market=ExchangeKind.SSE,
                interval=BarInterval.M5,
            ),
            payload=[],
        ),
        should_raise=True,
    )
    service = KlineSyncService(
        gateway=gateway,
        candle_repository=_InMemoryCandleRepository(),
        uow_factory=lambda: uow,
        tier_collection_service=_StubTierService(
            TieredSymbols(market=ExchangeKind.SSE, positions=("600000.SH",), candidates=(), others=())
        ),
        config=KlineSyncConfig(
            enabled_markets=[ExchangeKind.SSE],
            d1_window_days=730,
            m5_window_days=60,
            realtime_m5_interval_seconds=60,
            d1_sync_hour=17,
            backfill_batch_symbols=20,
            m5_backfill_chunk_days=20,
        ),
        now_provider=lambda: datetime(2026, 3, 23, 2, 35, 0, tzinfo=timezone.utc),
    )

    summary = await service.sync_realtime_m5_positions(ExchangeKind.SSE)

    assert summary["synced"] == 0
    assert summary["failed"] == 0
    assert summary["skipped"] == 1
    assert store.kline_sync_states["600000.SH:sse:5m"]["status"] == "failed"


def test_latest_completed_d1_on_weekend_uses_friday_for_a_share() -> None:
    now = datetime(2026, 3, 28, 4, 0, 0, tzinfo=timezone.utc)
    target = kline_sync_module._latest_completed_bar_start(now, ExchangeKind.SSE, BarInterval.D1)
    assert target is not None
    assert to_market_time(target, ExchangeKind.SSE).date().weekday() == 4


def test_latest_completed_d1_on_weekend_keeps_weekend_for_weekend_trading_market() -> None:
    now = datetime(2026, 3, 28, 4, 0, 0, tzinfo=timezone.utc)
    target = kline_sync_module._latest_completed_bar_start(now, "binance", BarInterval.D1)
    assert target is not None
    assert to_market_time(target, "binance").date() == to_market_time(now, "binance").date()
