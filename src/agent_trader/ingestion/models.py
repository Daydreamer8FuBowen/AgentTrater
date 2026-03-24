from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar

from agent_trader.domain.models import BarInterval, ExchangeKind


class DataCapability(str, Enum):
    """统一数据能力类型。"""

    # K 线（时间序列）数据能力
    KLINE = "kline"
    # 新闻/舆情数据能力
    NEWS = "news"
    # 财务报表 / 业绩数据能力
    FINANCIAL_REPORT = "financial_report"


@dataclass(slots=True, frozen=True)
class DataRouteKey:
    """用于优先级路由的维度键。"""

    capability: DataCapability  # 能力类型（KLINE / NEWS / FINANCIAL_REPORT）
    market: ExchangeKind | None = None  # 交易市场（如 SSE / SZSE），None 表示通配所有市场
    interval: BarInterval | None = None  # 时间间隔（如 M5/D1），仅对 KLINE 有意义

    def as_storage_key(self) -> str:
        market_value = self.market.value if self.market else "*"
        interval_value = self.interval.value if self.interval else "*"
        return f"{self.capability.value}:{market_value}:{interval_value}"


@dataclass(slots=True)
class KlineQuery:
    symbol: str  # 交易标的，例如 '000001.SZ' 或 '600000.SH'
    start_time: datetime  # 查询开始时间（包含）
    end_time: datetime  # 查询结束时间（包含）
    interval: BarInterval  # 周期，如 BarInterval.M5, BarInterval.D1
    market: ExchangeKind | None = None  # 可选：指定市场以约束路由
    adjusted: bool = False  # 是否使用前复权（True 表示 qfq）
    extra: dict[str, Any] = field(default_factory=dict)  # 可扩展的 provider-specific 参数


@dataclass(slots=True)
class NewsQuery:
    symbol: str | None  # 可选：按股票代码过滤新闻，None 表示不过滤
    start_time: datetime | None  # 可选：起始时间
    end_time: datetime | None  # 可选：结束时间
    market: ExchangeKind | None = None  # 可选：市场维度（新闻通常不区分市场）
    keywords: list[str] = field(default_factory=list)  # 关键词列表（OR 语义）
    extra: dict[str, Any] = field(default_factory=dict)  # 额外参数，例如来源或分页


@dataclass(slots=True)
class FinancialReportQuery:
    symbol: str  # 公司代码，必需
    start_time: datetime | None  # 查询起始时间（按报告日期或年份过滤）
    end_time: datetime | None  # 查询结束时间
    market: ExchangeKind | None = None  # 可选：市场维度
    extra: dict[str, Any] = field(default_factory=dict)  # 额外查询选项


@dataclass(slots=True)
class KlineRecord:
    """统一 K 线记录。"""

    symbol: str
    bar_time: datetime
    interval: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None
    amount: float | None
    change_pct: float | None
    turnover_rate: float | None
    adjusted: bool
    is_trading: bool | None = None


@dataclass(slots=True)
class BasicInfoRecord:
    """统一标的基础信息记录。

    字段说明：
    - symbol: 交易标的代码（例如 '000001.SZ' 或 '600000.SH'），唯一标识。
    - name: 公司/标的简称。
    - industry: 行业分类（可选）。
    - area: 地域/省份（可选）。
    - market: 交易市场标识（例如 'SSE', 'SZSE'），可为 None 表示未指定或通用。
    - list_date: 上市日期（datetime），如未知可为 None。
    - status: 上市状态（例如 'listed'、'delisted'、'suspended' 等）。
    - delist_date: 退市日期（datetime），如未退市为 None。
    - security_type: 证券类别（例如 'stock'、'fund'、'bond' 等），可为 None。
    """

    symbol: str
    name: str | None
    industry: str | None
    area: str | None
    market: str | None
    list_date: datetime | None
    status: str | None
    delist_date: datetime | None = None
    security_type: str | None = None


@dataclass(slots=True)
class NewsRecord:
    """统一新闻记录。"""

    published_at: datetime | None
    title: str
    content: str
    source_channel: str
    url: str | None
    symbols: list[str]


@dataclass(slots=True)
class FinancialReportRecord:
    """统一财报记录。"""

    symbol: str
    report_type: str
    report_date: datetime | None
    published_at: datetime | None
    report_year: int | None
    report_quarter: int | None
    metrics: dict[str, Any]


TRecord = TypeVar("TRecord")


@dataclass(slots=True)
class FetchResultBase(Generic[TRecord]):
    """统一数据抓取结果基类。"""

    source: str
    route_key: DataRouteKey
    payload: list[TRecord]
    data_kind: str = "generic"
    schema_version: str = "v1"
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class KlineCapabilityFetchResultBase(FetchResultBase[TRecord], Generic[TRecord]):
    """绑定到 KLINE capability 路由域的结果基类。"""


@dataclass(slots=True)
class KlineFetchResult(KlineCapabilityFetchResultBase[KlineRecord]):
    data_kind: str = field(init=False, default="kline")


@dataclass(slots=True)
class BasicInfoFetchResult(KlineCapabilityFetchResultBase[BasicInfoRecord]):
    data_kind: str = field(init=False, default="basic_info")


@dataclass(slots=True)
class NewsFetchResult(FetchResultBase[NewsRecord]):
    data_kind: str = field(init=False, default="news")


@dataclass(slots=True)
class FinancialReportFetchResult(FetchResultBase[FinancialReportRecord]):
    data_kind: str = field(init=False, default="financial_report")


DataFetchResult = KlineFetchResult | BasicInfoFetchResult | NewsFetchResult | FinancialReportFetchResult


@dataclass(slots=True)
class SourceCapabilitySpec:
    """声明数据源支持的能力范围。"""

    source: str  # 数据源名称
    capability: DataCapability  # 支持的能力类型（KLINE/NEWS/FINANCIAL_REPORT）
    markets: tuple[ExchangeKind, ...] = ()  # 支持的市场集合，空表示不区分
    intervals: tuple[BarInterval, ...] = ()  # 支持的周期集合，仅对 KLINE 有意义
