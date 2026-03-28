from __future__ import annotations

from typing import Protocol

from agent_trader.domain.models import ExchangeKind
from agent_trader.ingestion.models import (
    BasicInfoFetchResult,
    CompanyFinancialIndicatorFetchResult,
    CompanyIncomeStatementFetchResult,
    CompanyValuationFetchResult,
    DataRouteKey,
    KlineFetchResult,
    KlineQuery,
    SourceCapabilitySpec,
)


class UnifiedDataSource(Protocol):
    """统一数据源协议。

    架构说明：
    - 当前 ingestion 架构采用“单体多模块 + 协议约束”方式。
    - sources 层通过 Protocol 约束 provider 最小能力，路由层只依赖协议，不依赖具体实现类。
    - 本协议聚焦数据源注册维度：标识信息与能力声明。
    """

    name: str

    def capabilities(self) -> list[SourceCapabilitySpec]:
        """输入规范：无入参。
        输出规范：返回 SourceCapabilitySpec 列表，必须完整声明 source/capability/markets/intervals。
        """
        ...


class KlineDataSource(Protocol):
    """K 线域数据源协议。

    架构说明：
    - K 线与基础信息在当前契约中绑定到同一 capability（DataCapability.KLINE）。
    - 网关与选择器通过该协议进行统一调度，实现多源路由与顺序尝试。
    - provider 内部可做字段映射与时区转换，但输出必须符合统一模型。
    """

    async def fetch_klines_unified(self, query: KlineQuery) -> KlineFetchResult:
        """输入规范：
        - query.symbol 为统一证券代码（如 000001.SZ）。
        - query.start_time/query.end_time 为 UTC，且精确到分钟。
        - query.interval 必须是 provider 支持的周期。
        输出规范：
        - 返回 KlineFetchResult，payload 为 KlineRecord 列表。
        - payload 必须按 KlineRecord.bar_time 递增排序（从旧到新）。
        - route_key.capability 必须为 DataCapability.KLINE。
        - metadata["count"] 必须等于 len(payload)。
        """
        ...

    async def fetch_basic_info(
        self,
        market: ExchangeKind | None = None,
    ) -> BasicInfoFetchResult:
        """输入规范：
        - market 可为空；为空表示返回全市场基础信息。
        - 若指定 market，应按市场维度过滤结果。
        输出规范：
        - 返回 BasicInfoFetchResult，route_key.capability 仍为 DataCapability.KLINE。
        - metadata["count"] 必须等于 len(payload)。
        """
        ...


class CompanyDetailDataSource(Protocol):
    async def fetch_company_valuation_unified(
        self,
        symbol: str,
        market: ExchangeKind | None = None,
    ) -> CompanyValuationFetchResult:
        ...

    async def fetch_company_financial_indicators_unified(
        self,
        symbol: str,
        market: ExchangeKind | None = None,
    ) -> CompanyFinancialIndicatorFetchResult:
        ...

    async def fetch_company_income_statements_unified(
        self,
        symbol: str,
        market: ExchangeKind | None = None,
    ) -> CompanyIncomeStatementFetchResult:
        ...


class DataSourceSelector(Protocol):
    """数据源选择器协议。

    架构说明：
    - 选择器位于路由层，负责按 route_key 解析优先级并返回可尝试 source 名单。
    - sources 层与具体优先级存储解耦，避免 provider 直接处理路由策略。
    """

    async def select_sources(self, route_key: DataRouteKey) -> list[str]:
        """输入规范：
        - route_key 必须包含 capability；market/interval 作为可选维度参与匹配。
        输出规范：
        - 返回 source 名称列表，顺序代表调用优先级（由高到低）。
        """
        ...
