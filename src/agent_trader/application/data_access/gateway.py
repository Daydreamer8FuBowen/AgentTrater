from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from agent_trader.application.data_access.kline_utils import (
    MAX_KLINE_BARS,
    estimate_kline_count,
)
from agent_trader.domain.models import ExchangeKind
from agent_trader.ingestion.models import (
    BasicInfoFetchResult,
    CompanyFinancialIndicatorFetchResult,
    CompanyIncomeStatementFetchResult,
    CompanyValuationFetchResult,
    DataCapability,
    DataFetchResult,
    DataRouteKey,
    FinancialReportFetchResult,
    FinancialReportQuery,
    KlineFetchResult,
    KlineQuery,
    NewsFetchResult,
    NewsQuery,
)

logger = logging.getLogger(__name__)

TResult = TypeVar("TResult", bound=DataFetchResult)


@dataclass(slots=True, frozen=True)
class BasicInfoSourceFetchOutcome:
    """单个数据源 basic_info 拉取结果。"""

    source_name: str
    result: BasicInfoFetchResult | None
    error: str | None = None


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
    ) -> None:
        self._registry = registry
        self._priority_repository = priority_repository

    @property
    def registry(self) -> DataSourceRegistry:
        return self._registry

    async def select_sources(
        self,
        route_key: DataRouteKey,
        *,
        available_sources: list[str] | None = None,
    ) -> list[str]:
        route = await self._priority_repository.get(route_key)
        prioritized_sources = (
            route.priorities
            if route is not None and route.enabled and route.priorities
            else self._registry.names()
        )
        if not available_sources:
            return list(prioritized_sources)
        allowed_set = set(available_sources)
        return [source_name for source_name in prioritized_sources if source_name in allowed_set]

    async def execute(
        self,
        route_key: DataRouteKey,
        invoker: Callable[[str, object], Awaitable[TResult]],
        *,
        available_sources: list[str] | None = None,
    ) -> TResult:
        source_names = await self.select_sources(route_key, available_sources=available_sources)
        if not source_names:
            raise RuntimeError(f"No source registered for route={route_key.as_storage_key()}")

        route_id = route_key.as_storage_key()
        last_error: Exception | None = None

        for source_name in list(source_names):
            provider = self._registry.get(source_name)
            if provider is None:
                continue

            try:
                return await invoker(source_name, provider)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning(
                    "source failed route=%s source=%s error=%s",
                    route_id,
                    source_name,
                    str(exc),
                )

        raise RuntimeError(f"All sources failed for route={route_id}") from last_error

class DataAccessGateway:
    """统一数据访问门面，业务层仅依赖这个入口。"""

    def __init__(self, selector: SourceSelectionAdapter) -> None:
        self._selector = selector

    async def fetch_basic_info(self, market: ExchangeKind | None = None) -> BasicInfoFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            market=market,
            interval=None,
        )

        async def _invoke(_: str, provider: object) -> BasicInfoFetchResult:
            method = getattr(provider, "fetch_basic_info", None)
            if not callable(method):
                raise NotImplementedError(
                    f"provider={getattr(provider, 'name', 'unknown')} missing basic_info ability"
                )
            return await method(market=market)

        return await self._selector.execute(route_key, _invoke)

    async def fetch_company_valuation_unified(
        self,
        symbol: str,
        market: ExchangeKind | None = None,
    ) -> CompanyValuationFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.COMPANY_DETAIL,
            market=market,
            interval=None,
        )

        async def _invoke(_: str, provider: object) -> CompanyValuationFetchResult:
            method = getattr(provider, "fetch_company_valuation_unified", None)
            if not callable(method):
                raise NotImplementedError(
                    f"provider={getattr(provider, 'name', 'unknown')} missing company_valuation ability"
                )
            return await method(symbol=symbol, market=market)

        return await self._selector.execute(route_key, _invoke)

    async def fetch_company_financial_indicators_unified(
        self,
        symbol: str,
        market: ExchangeKind | None = None,
    ) -> CompanyFinancialIndicatorFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.COMPANY_DETAIL,
            market=market,
            interval=None,
        )

        async def _invoke(_: str, provider: object) -> CompanyFinancialIndicatorFetchResult:
            method = getattr(provider, "fetch_company_financial_indicators_unified", None)
            if not callable(method):
                raise NotImplementedError(
                    f"provider={getattr(provider, 'name', 'unknown')} missing company_financial_indicators ability"
                )
            return await method(symbol=symbol, market=market)

        return await self._selector.execute(route_key, _invoke)

    async def fetch_company_income_statements_unified(
        self,
        symbol: str,
        market: ExchangeKind | None = None,
    ) -> CompanyIncomeStatementFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.COMPANY_DETAIL,
            market=market,
            interval=None,
        )

        async def _invoke(_: str, provider: object) -> CompanyIncomeStatementFetchResult:
            method = getattr(provider, "fetch_company_income_statements_unified", None)
            if not callable(method):
                raise NotImplementedError(
                    f"provider={getattr(provider, 'name', 'unknown')} missing company_income_statements ability"
                )
            return await method(symbol=symbol, market=market)

        return await self._selector.execute(route_key, _invoke)

    async def fetch_basic_info_from_all_sources(
        self,
        market: ExchangeKind | None = None,
    ) -> list[BasicInfoSourceFetchOutcome]:
        """按优先顺序拉取所有可用源的 basic_info，并隔离单源失败。"""

        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            market=market,
            interval=None,
        )
        source_names = await self._selector.select_sources(route_key)
        for source_name in self._selector.registry.names():
            if source_name not in source_names:
                source_names.append(source_name)

        async def _fetch_one(source_name: str) -> BasicInfoSourceFetchOutcome:
            provider = self._selector.registry.get(source_name)
            if provider is None:
                return BasicInfoSourceFetchOutcome(
                    source_name=source_name,
                    result=None,
                    error="provider not found",
                )

            method = getattr(provider, "fetch_basic_info", None)
            if not callable(method):
                return BasicInfoSourceFetchOutcome(
                    source_name=source_name,
                    result=None,
                    error="missing basic_info ability",
                )

            try:
                result = await method(market=market)
                return BasicInfoSourceFetchOutcome(source_name=source_name, result=result)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "basic_info source failed route=%s source=%s error=%s",
                    route_key.as_storage_key(),
                    source_name,
                    str(exc),
                )
                return BasicInfoSourceFetchOutcome(
                    source_name=source_name,
                    result=None,
                    error=str(exc),
                )

        return await asyncio.gather(*[_fetch_one(name) for name in source_names])

    @staticmethod
    def _extract_available_sources(query: KlineQuery) -> list[str] | None:
        raw_value = query.extra.get("available_sources")
        if raw_value is None:
            raw_value = query.extra.get("sources")
        if raw_value is None:
            return None
        if not isinstance(raw_value, list):
            raise ValueError("query.extra.available_sources must be a list[str]")
        values = [item.strip() for item in raw_value if isinstance(item, str) and item.strip()]
        if not values:
            return None
        deduplicated: list[str] = []
        seen: set[str] = set()
        for source_name in values:
            if source_name not in seen:
                seen.add(source_name)
                deduplicated.append(source_name)
        return deduplicated

    async def fetch_klines(self, query: KlineQuery) -> KlineFetchResult:
        """K 线统一入口。

        可通过 query.extra 指定执行范围：
        - extra.available_sources: list[str]（推荐）
        - extra.sources: list[str]（兼容）
        当指定后，仅在该子集内按既有优先级顺序执行，并保持单源失败隔离。
        """
        estimated = estimate_kline_count(
            query.start_time,
            query.end_time,
            query.interval,
            query.market,
        )
        if estimated > MAX_KLINE_BARS:
            raise ValueError(
                f"K线单次请求预计返回 {estimated} 条，超过上限 {MAX_KLINE_BARS}；"
                "请缩小时间范围后重试"
            )

        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            market=query.market,
            interval=query.interval,
        )

        async def _invoke(_: str, provider: object) -> KlineFetchResult:
            method = getattr(provider, "fetch_klines_unified", None)
            if not callable(method):
                raise NotImplementedError(
                    f"provider={getattr(provider, 'name', 'unknown')} missing kline ability"
                )
            return await method(query)

        available_sources = self._extract_available_sources(query)
        return await self._selector.execute(
            route_key,
            _invoke,
            available_sources=available_sources,
        )

    async def fetch_news(self, query: NewsQuery) -> NewsFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.NEWS,
            market=query.market,
            interval=None,
        )

        async def _invoke(_: str, provider: object) -> NewsFetchResult:
            method = getattr(provider, "fetch_news_unified", None)
            if not callable(method):
                raise NotImplementedError(
                    f"provider={getattr(provider, 'name', 'unknown')} missing news ability"
                )
            return await method(query)

        return await self._selector.execute(route_key, _invoke)

    async def fetch_financial_reports(
        self,
        query: FinancialReportQuery,
    ) -> FinancialReportFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.FINANCIAL_REPORT,
            market=query.market,
            interval=None,
        )

        async def _invoke(_: str, provider: object) -> FinancialReportFetchResult:
            method = getattr(provider, "fetch_financial_reports_unified", None)
            if not callable(method):
                raise NotImplementedError(
                    f"provider={getattr(provider, 'name', 'unknown')}"
                    " missing financial_report ability"
                )
            return await method(query)

        return await self._selector.execute(route_key, _invoke)
