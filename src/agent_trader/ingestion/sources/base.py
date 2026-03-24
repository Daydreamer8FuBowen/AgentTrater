from __future__ import annotations

from typing import Protocol

from agent_trader.domain.models import ExchangeKind
from agent_trader.ingestion.models import (
    BasicInfoFetchResult,
    DataRouteKey,
    FinancialReportFetchResult,
    FinancialReportQuery,
    KlineFetchResult,
    KlineQuery,
    NewsFetchResult,
    NewsQuery,
    SourceCapabilitySpec,
)


class UnifiedDataSource(Protocol):
    """统一数据源协议，按能力提供可选实现。"""

    name: str

    def capabilities(self) -> list[SourceCapabilitySpec]: ...


class KlineDataSource(Protocol):
    async def fetch_klines_unified(self, query: KlineQuery) -> KlineFetchResult: ...

    # 获取数据源可提供的标的/基础信息（例如股票基本信息），
    # 该能力和 KlineDataSource 绑定出现，不单独拆分协议。
    async def fetch_basic_info(self, market: ExchangeKind | None = None) -> BasicInfoFetchResult: ...


class NewsDataSource(Protocol):
    async def fetch_news_unified(self, query: NewsQuery) -> NewsFetchResult: ...


class FinancialReportDataSource(Protocol):
    async def fetch_financial_reports_unified(
        self,
        query: FinancialReportQuery,
    ) -> FinancialReportFetchResult: ...


class DataSourceSelector(Protocol):
    """路由策略适配器协议。"""

    async def select_sources(self, route_key: DataRouteKey) -> list[str]: ...