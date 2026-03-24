from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from agent_trader.domain.models import BarInterval, ExchangeKind, TriggerKind


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
class SourceFetchResult:
    """统一结果容器，暂不约束 payload 结构。"""

    source: str  # 返回数据的来源标识（provider.name）
    route_key: DataRouteKey  # 本次请求对应的路由键
    payload: list[dict[str, Any]]  # 未经严格约束的原始或归一化记录列表
    fetched_at: datetime = field(default_factory=datetime.utcnow)  # 抓取时间（UTC）
    metadata: dict[str, Any] = field(default_factory=dict)  # 附带元数据（如 count、freq、symbol）


@dataclass(slots=True)
class SourceCapabilitySpec:
    """声明数据源支持的能力范围。"""

    source: str  # 数据源名称
    capability: DataCapability  # 支持的能力类型（KLINE/NEWS/FINANCIAL_REPORT）
    markets: tuple[ExchangeKind, ...] = ()  # 支持的市场集合，空表示不区分
    intervals: tuple[BarInterval, ...] = ()  # 支持的周期集合，仅对 KLINE 有意义


@dataclass(slots=True)
class RawEvent:
    source: str  # 事件来源标识，例如 provider 名称或消息队列主题
    payload: dict[str, Any]  # 原始事件负载，结构随来源而异
    received_at: datetime = field(default_factory=datetime.utcnow)  # 接收时间（UTC）
    id: UUID = field(default_factory=uuid4)  # 事件唯一标识


@dataclass(slots=True)
class NormalizedEvent:
    trigger_kind: TriggerKind  # 触发类型，用于路由和处理
    symbol: str  # 相关标的代码
    title: str  # 事件/新闻标题
    content: str  # 事件正文或摘要
    metadata: dict[str, Any]  # 附加字段（来源、原始 id、置信度等）
    id: UUID = field(default_factory=uuid4)  # 归一化事件唯一 id


@dataclass(slots=True)
class ResearchTrigger:
    trigger_kind: TriggerKind  # 触发器类型（例如 'price_spike'）
    symbol: str  # 相关股票代码
    summary: str  # 简短的触发器摘要，供快速阅读
    metadata: dict[str, Any]  # 额外上下文，例如触发阈值或来源
    id: UUID = field(default_factory=uuid4)  # 唯一标识