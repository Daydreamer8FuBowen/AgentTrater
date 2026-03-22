from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from agent_trader.domain.models import BarInterval, ExchangeKind, TriggerKind


class DataCapability(str, Enum):
    """统一数据能力类型。"""

    KLINE = "kline"
    NEWS = "news"
    FINANCIAL_REPORT = "financial_report"


class FetchMode(str, Enum):
    """统一获取模式。"""

    REALTIME = "realtime"
    HISTORY = "history"
    INCREMENTAL = "incremental"


@dataclass(slots=True, frozen=True)
class DataRouteKey:
    """用于优先级路由的维度键。"""

    capability: DataCapability
    mode: FetchMode
    market: ExchangeKind | None = None
    interval: BarInterval | None = None

    def as_storage_key(self) -> str:
        market_value = self.market.value if self.market else "*"
        interval_value = self.interval.value if self.interval else "*"
        return f"{self.capability.value}:{self.mode.value}:{market_value}:{interval_value}"


@dataclass(slots=True)
class KlineQuery:
    symbol: str
    start_time: datetime
    end_time: datetime
    interval: BarInterval
    mode: FetchMode
    market: ExchangeKind | None = None
    adjusted: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NewsQuery:
    symbol: str | None
    start_time: datetime | None
    end_time: datetime | None
    mode: FetchMode
    market: ExchangeKind | None = None
    keywords: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FinancialReportQuery:
    symbol: str
    start_time: datetime | None
    end_time: datetime | None
    mode: FetchMode
    market: ExchangeKind | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SourceFetchResult:
    """统一结果容器，暂不约束 payload 结构。"""

    source: str
    route_key: DataRouteKey
    payload: list[dict[str, Any]]
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SourceCapabilitySpec:
    """声明数据源支持的能力范围。"""

    source: str
    capability: DataCapability
    modes: tuple[FetchMode, ...]
    markets: tuple[ExchangeKind, ...] = ()
    intervals: tuple[BarInterval, ...] = ()


@dataclass(slots=True)
class RawEvent:
    source: str
    payload: dict[str, Any]
    received_at: datetime = field(default_factory=datetime.utcnow)
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class NormalizedEvent:
    trigger_kind: TriggerKind
    symbol: str
    title: str
    content: str
    metadata: dict[str, Any]
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class ResearchTrigger:
    trigger_kind: TriggerKind
    symbol: str
    summary: str
    metadata: dict[str, Any]
    id: UUID = field(default_factory=uuid4)