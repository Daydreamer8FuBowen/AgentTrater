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
    FetchMode,
    KlineQuery,
    SourceFetchResult,
)


@dataclass
class _RouteDoc:
    route_id: str
    priorities: list[str]
    enabled: bool = True


@dataclass
class _HealthDoc:
    route_id: str
    source: str
    consecutive_failures: int = 0
    circuit_open_until: datetime | None = None


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


class _InMemoryRouteHealthRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], _HealthDoc] = {}

    async def get(self, route_id: str, source: str) -> _HealthDoc | None:
        return self._items.get((route_id, source))

    async def record_success(self, route_id: str, source: str) -> None:
        self._items[(route_id, source)] = _HealthDoc(route_id=route_id, source=source, consecutive_failures=0)

    async def record_failure(self, route_id: str, source: str, *, error_message: str, open_until: datetime | None) -> None:  # noqa: ARG002
        prev = self._items.get((route_id, source))
        failures = 1 if prev is None else prev.consecutive_failures + 1
        self._items[(route_id, source)] = _HealthDoc(
            route_id=route_id,
            source=source,
            consecutive_failures=failures,
            circuit_open_until=open_until,
        )

    async def list_retryable(self, *, now: datetime, limit: int = 100) -> list[_HealthDoc]:  # noqa: ARG002
        return []

    async def clear_circuit(self, route_id: str, source: str) -> None:
        state = self._items.get((route_id, source))
        if state is None:
            return
        state.circuit_open_until = None
        state.consecutive_failures = 0


class _FailingProvider:
    name = "primary"

    async def fetch_klines_unified(self, query: KlineQuery) -> SourceFetchResult:  # noqa: ARG002
        raise RuntimeError("source down")


class _SuccessProvider:
    name = "fallback"

    async def fetch_klines_unified(self, query: KlineQuery) -> SourceFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            mode=query.mode,
            market=query.market,
            interval=query.interval,
        )
        return SourceFetchResult(source=self.name, route_key=route_key, payload=[{"symbol": query.symbol}])


@pytest.mark.asyncio
async def test_gateway_fallback_and_promote_success_source() -> None:
    route_key = DataRouteKey(
        capability=DataCapability.KLINE,
        mode=FetchMode.REALTIME,
        market=ExchangeKind.SSE,
        interval=BarInterval.M5,
    )

    priority_repo = _InMemoryPriorityRepository()
    health_repo = _InMemoryRouteHealthRepository()
    await priority_repo.upsert(route_key, priorities=["primary", "fallback"])

    registry = DataSourceRegistry()
    registry.register(_FailingProvider())
    registry.register(_SuccessProvider())

    selector = SourceSelectionAdapter(
        registry=registry,
        priority_repository=priority_repo,
        route_health_repository=health_repo,
        failure_threshold=2,
        circuit_open_seconds=60,
        promotion_step=1,
        promote_on_success=True,
    )
    gateway = DataAccessGateway(selector)

    query = KlineQuery(
        symbol="000001.SZ",
        start_time=datetime(2026, 1, 1),
        end_time=datetime(2026, 1, 2),
        interval=BarInterval.M5,
        mode=FetchMode.REALTIME,
        market=ExchangeKind.SSE,
    )
    result = await gateway.fetch_klines(query)

    assert result.source == "fallback"
    updated = await priority_repo.get(route_key)
    assert updated is not None
    assert updated.priorities == ["fallback", "primary"]


@pytest.mark.asyncio
async def test_selection_adapter_circuit_open_after_threshold() -> None:
    route_key = DataRouteKey(
        capability=DataCapability.KLINE,
        mode=FetchMode.REALTIME,
        market=ExchangeKind.SSE,
        interval=BarInterval.M5,
    )

    priority_repo = _InMemoryPriorityRepository()
    health_repo = _InMemoryRouteHealthRepository()
    await priority_repo.upsert(route_key, priorities=["primary", "fallback"])

    registry = DataSourceRegistry()
    registry.register(_FailingProvider())
    registry.register(_SuccessProvider())

    selector = SourceSelectionAdapter(
        registry=registry,
        priority_repository=priority_repo,
        route_health_repository=health_repo,
        failure_threshold=1,
        circuit_open_seconds=60,
        promotion_step=1,
        promote_on_success=False,
    )

    query = KlineQuery(
        symbol="000001.SZ",
        start_time=datetime(2026, 1, 1),
        end_time=datetime(2026, 1, 2),
        interval=BarInterval.M5,
        mode=FetchMode.REALTIME,
        market=ExchangeKind.SSE,
    )

    gateway = DataAccessGateway(selector)
    result = await gateway.fetch_klines(query)
    assert result.source == "fallback"

    state = await health_repo.get(route_key.as_storage_key(), "primary")
    assert state is not None
    assert state.circuit_open_until is not None
