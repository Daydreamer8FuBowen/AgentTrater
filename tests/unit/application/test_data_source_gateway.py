from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pytest

from agent_trader.application.data_access.gateway import (
    DataAccessGateway,
    DataSourceRegistry,
    SourceSelectionAdapter,
)
from agent_trader.domain.models import BarInterval, ExchangeKind
from agent_trader.ingestion.models import (
    DataCapability,
    DataRouteKey,
    KlineFetchResult,
    KlineQuery,
    KlineRecord,
)


@dataclass
class _RouteDoc:
    route_id: str
    priorities: list[str]
    enabled: bool = True


class _InMemoryPriorityRepository:
    def __init__(self) -> None:
        self._items: dict[str, _RouteDoc] = {}

    async def get(self, route_key: DataRouteKey) -> _RouteDoc | None:
        return self._items.get(route_key.as_storage_key())

    async def upsert(
        self,
        route_key: DataRouteKey,
        *,
        priorities: list[str],
        enabled: bool = True,
        metadata: dict[str, object] | None = None,
    ) -> _RouteDoc:  # noqa: ARG002
        route = _RouteDoc(
            route_id=route_key.as_storage_key(),
            priorities=list(priorities),
            enabled=enabled,
        )
        self._items[route.route_id] = route
        return route

    async def reorder(self, route_key: DataRouteKey, *, priorities: list[str]) -> None:
        route_id = route_key.as_storage_key()
        route = self._items[route_id]
        route.priorities = list(priorities)


class _PrimaryProvider:
    name = "primary"

    async def fetch_klines_unified(self, query: KlineQuery) -> KlineFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            market=query.market,
            interval=query.interval,
        )
        return KlineFetchResult(
            source=self.name,
            route_key=route_key,
            payload=[
                KlineRecord(
                    symbol=query.symbol,
                    bar_time=query.start_time,
                    interval=query.interval.value,
                    open=None,
                    high=None,
                    low=None,
                    close=None,
                    volume=None,
                    amount=None,
                    change_pct=None,
                    turnover_rate=None,
                    adjusted=query.adjusted,
                )
            ],
        )


class _FallbackProvider:
    name = "fallback"

    async def fetch_klines_unified(self, query: KlineQuery) -> KlineFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            market=query.market,
            interval=query.interval,
        )
        return KlineFetchResult(
            source=self.name,
            route_key=route_key,
            payload=[
                KlineRecord(
                    symbol=query.symbol,
                    bar_time=query.start_time,
                    interval=query.interval.value,
                    open=None,
                    high=None,
                    low=None,
                    close=None,
                    volume=None,
                    amount=None,
                    change_pct=None,
                    turnover_rate=None,
                    adjusted=query.adjusted,
                )
            ],
        )


@pytest.mark.asyncio
async def test_data_source_registry_basic_register_and_names() -> None:
    registry = DataSourceRegistry()
    primary = _PrimaryProvider()
    fallback = _FallbackProvider()

    registry.register(primary)
    registry.register(fallback)

    assert registry.get("primary") is primary
    assert registry.get("fallback") is fallback
    assert registry.names() == ["primary", "fallback"]


@pytest.mark.asyncio
async def test_source_selection_adapter_basic_priority_config() -> None:
    route_key = DataRouteKey(
        capability=DataCapability.KLINE,
        market=ExchangeKind.SSE,
        interval=BarInterval.M5,
    )
    priority_repo = _InMemoryPriorityRepository()
    await priority_repo.upsert(route_key, priorities=["primary", "fallback"])

    registry = DataSourceRegistry()
    registry.register(_PrimaryProvider())
    registry.register(_FallbackProvider())
    selector = SourceSelectionAdapter(registry=registry, priority_repository=priority_repo)

    selected = await selector.select_sources(route_key)

    assert selected == ["primary", "fallback"]


@pytest.mark.asyncio
async def test_source_selection_adapter_filters_available_sources() -> None:
    route_key = DataRouteKey(
        capability=DataCapability.KLINE,
        market=ExchangeKind.SSE,
        interval=BarInterval.M5,
    )
    priority_repo = _InMemoryPriorityRepository()
    await priority_repo.upsert(route_key, priorities=["primary", "fallback"])

    registry = DataSourceRegistry()
    registry.register(_PrimaryProvider())
    registry.register(_FallbackProvider())
    selector = SourceSelectionAdapter(registry=registry, priority_repository=priority_repo)

    selected = await selector.select_sources(route_key, available_sources=["fallback", "ghost"])

    assert selected == ["fallback"]


@pytest.mark.asyncio
async def test_data_access_gateway_fetch_klines_with_available_sources() -> None:
    route_key = DataRouteKey(
        capability=DataCapability.KLINE,
        market=ExchangeKind.SSE,
        interval=BarInterval.M5,
    )
    priority_repo = _InMemoryPriorityRepository()
    await priority_repo.upsert(route_key, priorities=["primary", "fallback"])

    registry = DataSourceRegistry()
    registry.register(_PrimaryProvider())
    registry.register(_FallbackProvider())
    selector = SourceSelectionAdapter(registry=registry, priority_repository=priority_repo)
    gateway = DataAccessGateway(selector)

    query = KlineQuery(
        symbol="000001.SZ",
        start_time=datetime(2026, 1, 1),
        end_time=datetime(2026, 1, 2),
        interval=BarInterval.M5,
        market=ExchangeKind.SSE,
        extra={"available_sources": ["fallback"]},
    )

    result = await gateway.fetch_klines(query)

    assert result.source == "fallback"
