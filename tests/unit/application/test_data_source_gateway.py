from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pytest

from agent_trader.application.services.data_source_gateway import (
    DataAccessGateway,
    DataSourceRegistry,
    SourceSelectionAdapter,
)
from agent_trader.domain.models import BarInterval, ExchangeKind
from agent_trader.ingestion.models import (
    DataCapability,
    DataRouteKey,
    KlineQuery,
    SourceFetchResult,
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

    async def upsert(self, route_key: DataRouteKey, *, priorities: list[str], enabled: bool = True, metadata: dict | None = None) -> _RouteDoc:  # noqa: ARG002
        route = _RouteDoc(route_id=route_key.as_storage_key(), priorities=list(priorities), enabled=enabled)
        self._items[route.route_id] = route
        return route

    async def reorder(self, route_key: DataRouteKey, *, priorities: list[str]) -> None:
        route_id = route_key.as_storage_key()
        route = self._items[route_id]
        route.priorities = list(priorities)


class _FailingProvider:
    name = "primary"

    async def fetch_klines_unified(self, query: KlineQuery) -> SourceFetchResult:  # noqa: ARG002
        raise RuntimeError("source down")


class _SuccessProvider:
    name = "fallback"

    async def fetch_klines_unified(self, query: KlineQuery) -> SourceFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            market=query.market,
            interval=query.interval,
        )
        return SourceFetchResult(source=self.name, route_key=route_key, payload=[{"symbol": query.symbol}])


class _PrimarySuccessProvider:
    name = "primary"

    async def fetch_klines_unified(self, query: KlineQuery) -> SourceFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            market=query.market,
            interval=query.interval,
        )
        return SourceFetchResult(source=self.name, route_key=route_key, payload=[{"symbol": query.symbol}])


@pytest.mark.asyncio
async def test_gateway_fallback_and_promote_success_source() -> None:
    route_key = DataRouteKey(
        capability=DataCapability.KLINE,
        market=ExchangeKind.SSE,
        interval=BarInterval.M5,
    )

    priority_repo = _InMemoryPriorityRepository()
    await priority_repo.upsert(route_key, priorities=["primary", "fallback"])

    registry = DataSourceRegistry()
    registry.register(_FailingProvider())
    registry.register(_SuccessProvider())

    selector = SourceSelectionAdapter(
        registry=registry,
        priority_repository=priority_repo,
    )
    gateway = DataAccessGateway(selector)

    query = KlineQuery(
        symbol="000001.SZ",
        start_time=datetime(2026, 1, 1),
        end_time=datetime(2026, 1, 2),
        interval=BarInterval.M5,
        market=ExchangeKind.SSE,
    )
    result = await gateway.fetch_klines(query)

    assert result.source == "fallback"
    updated = await priority_repo.get(route_key)
    assert updated is not None
    assert updated.priorities == ["fallback", "primary"]


@pytest.mark.asyncio
async def test_gateway_primary_success_keeps_priority_order() -> None:
    route_key = DataRouteKey(
        capability=DataCapability.KLINE,
        market=ExchangeKind.SSE,
        interval=BarInterval.M5,
    )

    priority_repo = _InMemoryPriorityRepository()
    await priority_repo.upsert(route_key, priorities=["primary", "fallback"])

    registry = DataSourceRegistry()
    registry.register(_PrimarySuccessProvider())
    registry.register(_SuccessProvider())

    selector = SourceSelectionAdapter(
        registry=registry,
        priority_repository=priority_repo,
    )

    query = KlineQuery(
        symbol="000001.SZ",
        start_time=datetime(2026, 1, 1),
        end_time=datetime(2026, 1, 2),
        interval=BarInterval.M5,
        market=ExchangeKind.SSE,
    )

    gateway = DataAccessGateway(selector)
    result = await gateway.fetch_klines(query)
    assert result.source == "primary"

    updated = await priority_repo.get(route_key)
    assert updated is not None
    assert updated.priorities == ["primary", "fallback"]
