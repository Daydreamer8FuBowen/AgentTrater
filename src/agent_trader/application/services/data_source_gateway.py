from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from agent_trader.ingestion.models import (
    DataCapability,
    DataRouteKey,
    FinancialReportQuery,
    KlineQuery,
    NewsQuery,
    SourceFetchResult,
)

logger = logging.getLogger(__name__)


class DataSourceRegistry:
    """统一数据源注册表。"""

    def __init__(self) -> None:
        self._providers: dict[str, object] = {}

    def register(self, provider: object, *, name: str | None = None) -> None:
        provider_name = name or getattr(provider, "name", None)
        if not provider_name:
            raise ValueError("provider 必须具备 name 属性或显式传入 name")
        self._providers[provider_name] = provider

    def get(self, name: str) -> object | None:
        return self._providers.get(name)

    def names(self) -> list[str]:
        return list(self._providers.keys())


class SourceSelectionAdapter:
    """按路由键从 Mongo 优先级链中选择可用源。"""

    def __init__(
        self,
        *,
        registry: DataSourceRegistry,
        priority_repository: Any,
        route_health_repository: Any,
        failure_threshold: int,
        circuit_open_seconds: int,
        promotion_step: int,
        promote_on_success: bool,
    ) -> None:
        self._registry = registry
        self._priority_repository = priority_repository
        self._route_health_repository = route_health_repository
        self._failure_threshold = max(1, failure_threshold)
        self._circuit_open_seconds = max(1, circuit_open_seconds)
        self._promotion_step = max(1, promotion_step)
        self._promote_on_success = promote_on_success

    async def select_sources(self, route_key: DataRouteKey) -> list[str]:
        route = await self._priority_repository.get(route_key)
        if route is not None and route.enabled and route.priorities:
            return route.priorities
        return self._registry.names()

    async def execute(self, route_key: DataRouteKey, invoker: Any) -> SourceFetchResult:
        source_names = await self.select_sources(route_key)
        if not source_names:
            raise RuntimeError(f"No source registered for route={route_key.as_storage_key()}")

        route_id = route_key.as_storage_key()
        now = datetime.utcnow()
        last_error: Exception | None = None

        for index, source_name in enumerate(source_names):
            provider = self._registry.get(source_name)
            if provider is None:
                continue

            health = await self._route_health_repository.get(route_id, source_name)
            if health is not None and health.circuit_open_until and health.circuit_open_until > now:
                continue

            try:
                result: SourceFetchResult = await invoker(source_name, provider)
                await self._route_health_repository.record_success(route_id, source_name)
                if self._promote_on_success and index > 0:
                    await self._promote(route_key=route_key, source_name=source_name)
                return result
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                open_until = None
                current_consecutive = 0 if health is None else health.consecutive_failures
                if current_consecutive + 1 >= self._failure_threshold:
                    open_until = now + timedelta(seconds=self._circuit_open_seconds)
                await self._route_health_repository.record_failure(
                    route_id,
                    source_name,
                    error_message=str(exc),
                    open_until=open_until,
                )
                logger.warning(
                    "source failed route=%s source=%s error=%s",
                    route_id,
                    source_name,
                    str(exc),
                )

        raise RuntimeError(f"All sources failed for route={route_id}") from last_error

    async def _promote(self, *, route_key: DataRouteKey, source_name: str) -> None:
        route = await self._priority_repository.get(route_key)
        if route is None or source_name not in route.priorities:
            return

        priorities = list(route.priorities)
        old_index = priorities.index(source_name)
        new_index = max(0, old_index - self._promotion_step)
        if old_index == new_index:
            return

        priorities.pop(old_index)
        priorities.insert(new_index, source_name)
        await self._priority_repository.reorder(route_key, priorities=priorities)


class DataAccessGateway:
    """统一数据访问门面，业务层仅依赖这个入口。"""

    def __init__(self, selector: SourceSelectionAdapter) -> None:
        self._selector = selector

    async def fetch_klines(self, query: KlineQuery) -> SourceFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            mode=query.mode,
            market=query.market,
            interval=query.interval,
        )

        async def _invoke(_: str, provider: object) -> SourceFetchResult:
            method = getattr(provider, "fetch_klines_unified", None)
            if not callable(method):
                raise NotImplementedError(f"provider={getattr(provider, 'name', 'unknown')} missing kline ability")
            return await method(query)

        return await self._selector.execute(route_key, _invoke)

    async def fetch_news(self, query: NewsQuery) -> SourceFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.NEWS,
            mode=query.mode,
            market=query.market,
            interval=None,
        )

        async def _invoke(_: str, provider: object) -> SourceFetchResult:
            method = getattr(provider, "fetch_news_unified", None)
            if not callable(method):
                raise NotImplementedError(f"provider={getattr(provider, 'name', 'unknown')} missing news ability")
            return await method(query)

        return await self._selector.execute(route_key, _invoke)

    async def fetch_financial_reports(self, query: FinancialReportQuery) -> SourceFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.FINANCIAL_REPORT,
            mode=query.mode,
            market=query.market,
            interval=None,
        )

        async def _invoke(_: str, provider: object) -> SourceFetchResult:
            method = getattr(provider, "fetch_financial_reports_unified", None)
            if not callable(method):
                raise NotImplementedError(
                    f"provider={getattr(provider, 'name', 'unknown')} missing financial_report ability"
                )
            return await method(query)

        return await self._selector.execute(route_key, _invoke)
