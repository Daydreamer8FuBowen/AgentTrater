from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from agent_trader.core.time import utc_now


class TriggerKind(str, Enum):
    """系统的统一触发入口，后续采集链路和 Agent 路由都基于它分流。"""

    NEWS = "news"
    ANNOUNCEMENT = "announcement"
    DISCUSSION = "discussion"
    INDICATOR = "indicator"


class CandidateStatus(str, Enum):
    """候选池状态机的基础状态枚举。"""

    DRAFT = "draft"
    WATCHING = "watching"
    RESEARCHING = "researching"
    SHORTLISTED = "shortlisted"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class MemoryKind(str, Enum):
    """区分单次运行记忆和长期沉淀记忆。"""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"


class ExchangeKind(str, Enum):
    """统一标识 K 线所属市场或交易所。

    设计这个枚举的目的不是穷举所有全球交易所，而是先给系统建立一套稳定的
    “跨数据源、跨资产类别”的归一化口径。后续无论数据来自券商 API、交易所
    行情接口还是第三方聚合商，最终都要映射到这里，避免在回测、因子计算和
    存储层出现多套 market/exchange 字段并存的情况。

    约定：
    1. 优先表达“交易发生在哪个市场/交易所”。
    2. 如果上游数据无法准确识别，则降级到 OTHER。
    3. 不建议直接把上游原始字符串写进业务层，应在采集层完成归一化映射。
    """

    SSE = "sse"
    SZSE = "szse"
    HKEX = "hkex"
    NASDAQ = "nasdaq"
    NYSE = "nyse"
    BINANCE = "binance"
    OKX = "okx"
    OTHER = "other"


class AssetClass(str, Enum):
    """统一标识交易标的类别。

    这个枚举主要服务于两类场景：
    1. 不同资产在指标、回测、风控上的处理逻辑不同。
    2. 同一个 symbol 在不同市场上下文中可能需要不同解释。

    当前先收敛为三类核心资产：
    - stock: 股票与股票型产品
    - crypto: 加密货币，通常是 7x24 连续交易
    - bond: 债券类资产

    因此资产类别应在 domain 层显式建模，而不是散落在业务代码里做字符串判断。
    """

    STOCK = "stock"
    CRYPTO = "crypto"
    BOND = "bond"


class BarInterval(str, Enum):
    """统一 K 线周期定义。

    这个枚举承担两个职责：
    1. 统一采集、存储、查询和指标计算中的周期标识。
    2. 避免出现 `1min`、`1m`、`minute_1`、`M1` 等多套口径混用。

    命名约定：
    - M* 表示分钟级
    - H* 表示小时级
    - D1/W1/MN1 表示日、周、月

    存储到 Influx 等时序库时，统一使用 value，例如 `1m`、`1d`。
    """

    M1 = "1m"
    M3 = "3m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"
    MN1 = "1mo"


@dataclass(slots=True)
class Opportunity:
    """触发事件经过标准化后形成的研究机会。"""

    symbol: str
    trigger_kind: TriggerKind
    summary: str
    confidence: float
    source_ref: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class ResearchTask:
    """由机会衍生出的研究任务，是后续 graph 运行的最小调度单元。"""

    opportunity_id: UUID
    trigger_kind: TriggerKind
    payload: dict[str, Any]
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class Candidate:
    """研究结果进入候选池后的实体，用于后续打分、约束和筛选。"""

    symbol: str
    thesis: str
    status: CandidateStatus
    score: float
    constraints: list[str]
    id: UUID = field(default_factory=uuid4)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class StrategyConstraint:
    """策略层的显式约束规则，后续可映射到风格、风险和持仓约束。"""

    name: str
    rule: str
    enabled: bool = True
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class MemoryRecord:
    """Agent 运行后的记忆沉淀记录。"""

    kind: MemoryKind
    content: str
    metadata: dict[str, Any]
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class BacktestRun:
    """一次回测任务的元数据与结果摘要。"""

    strategy_name: str
    started_at: datetime
    ended_at: datetime | None
    metrics: dict[str, float]
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class RepairTask:
    """回测发现问题后进入修复闭环的任务。"""

    backtest_run_id: UUID
    issue_summary: str
    proposed_fix: str
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class SignalSnapshot:
    """某一时刻的指标或特征快照，主要用于时序分析与回放。"""

    symbol: str
    values: dict[str, float]
    observed_at: datetime
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class Candle:
    """统一 K 线 domain。

    这层只表达业务语义，不绑定任何特定数据源字段名，
    便于采集层、回测层、指标层和存储层共用同一对象。
    """

    # 标的标识。建议在同一市场内采用统一编码规范，避免 AAPL / US.AAPL 之类的混用。
    symbol: str

    # K 线周期，例如 1m、1h、1d。
    interval: BarInterval

    # bar 开始时间，作为时序库存储时的主时间戳。
    open_time: datetime

    # bar 结束时间，便于范围查询、补数检查和回放。
    close_time: datetime

    # OHLC 四价。
    open_price: float
    high_price: float
    low_price: float
    close_price: float

    # 成交量。
    volume: float

    # 可选成交额，部分源没有时允许为空。
    turnover: float | None = None

    # 可选成交笔数。
    trade_count: int | None = None

    # 资产类别默认按股票处理，采集层应尽量显式覆盖。
    asset_class: AssetClass = AssetClass.STOCK

    # 交易所/市场默认 unknown-like 降级到 OTHER。
    exchange: ExchangeKind = ExchangeKind.OTHER

    # 是否复权。默认 False，避免误把未说明口径的数据当成复权数据。
    adjusted: bool = False

    # 数据来源标识，用于问题排查和多源对账。
    source: str = "unknown"

    def to_ohlcv(self) -> dict[str, float]:
        """返回指标计算常用的 OHLCV 结构。

        这个方法的目的不是替代 Candle 本身，而是给指标引擎、特征工程或第三方技术分析库
        提供一个最小兼容结构，避免调用方到处手写字段映射。
        """

        return {
            "open": self.open_price,
            "high": self.high_price,
            "low": self.low_price,
            "close": self.close_price,
            "volume": self.volume,
        }
