from __future__ import annotations

from typing import Protocol

from agent_trader.ingestion.models import (
    DataRouteKey,
    FinancialReportQuery,
    KlineQuery,
    NewsQuery,
    RawEvent,
    SourceCapabilitySpec,
    SourceFetchResult,
)


class SourceAdapter(Protocol):
    """兼容现有 ingestion 链路的基础协议。"""

    name: str

    async def fetch(self) -> list[RawEvent]: ...


class UnifiedDataSource(Protocol):
    """统一数据源协议，按能力提供可选实现。"""

    name: str

    def capabilities(self) -> list[SourceCapabilitySpec]: ...


class KlineDataSource(Protocol):
    async def fetch_klines_unified(self, query: KlineQuery) -> SourceFetchResult: ...

    # 获取数据源可提供的标的/基础信息（例如股票基本信息），
    # 返回 RawEvent 列表以保持和现有入库/规范化链路兼容。
    async def fetch_basic_info(self) -> list[RawEvent]: ...


class NewsDataSource(Protocol):
    async def fetch_news_unified(self, query: NewsQuery) -> SourceFetchResult: ...


class FinancialReportDataSource(Protocol):
    async def fetch_financial_reports_unified(
        self,
        query: FinancialReportQuery,
    ) -> SourceFetchResult: ...


class DataSourceSelector(Protocol):
    """路由策略适配器协议。"""

    async def select_sources(self, route_key: DataRouteKey) -> list[str]: ...