from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol

from agent_trader.domain.models import Candidate, Candle, MemoryRecord, SignalSnapshot, ExchangeKind
from agent_trader.ingestion.models import DataRouteKey


class TaskRunRepository(Protocol):
    """任务运行摘要仓储接口。"""

    async def add(self, task_run: Any) -> Any: ...
    async def get(self, run_id: str) -> Any | None: ...
    async def mark_running(self, run_id: str) -> None: ...
    async def mark_completed(self, run_id: str, *, result_summary: str | None) -> None: ...
    async def mark_failed(self, run_id: str, *, error_message: str) -> None: ...


class TaskEventRepository(Protocol):
    """任务执行事件仓储接口。"""

    async def add(self, event: Any) -> Any: ...


class TaskArtifactRepository(Protocol):
    """任务执行产物仓储接口。"""

    async def add(self, artifact: Any) -> Any: ...


class NewsRepository(Protocol):
    """新闻条目的读写接口。"""

    async def add(self, news: Any) -> Any: ...
    async def add_many(self, items: Sequence[Any]) -> Sequence[Any]: ...
    async def exists_by_dedupe_key(self, dedupe_key: str) -> bool: ...


class BasicInfoRepository(Protocol):
    """标的基础信息快照仓储接口。"""

    async def upsert_many_by_symbol(self, items: Sequence[Any]) -> dict[str, int]: ...
    async def list_symbols_by_market(self, market: ExchangeKind) -> list[str]: ...
    async def get_active_stock_symbols(self, market: ExchangeKind) -> list[str]: ...
    async def update_company_details(self, symbol: str, details: dict[str, Any]) -> None: ...
    async def get_available_sources_by_symbol(self, symbol: str) -> list[str] | None: ...


class CandidateRepository(Protocol):
    """候选池查询与写入接口。"""

    async def upsert(self, candidate: Candidate) -> Candidate: ...
    async def list_active(self) -> Sequence[Candidate]: ...


class PositionRepository(Protocol):
    """持仓查询与写入接口（与策略无关）。"""

    async def upsert(self, position: Any) -> Any: ...
    async def list_active(self) -> Sequence[Any]: ...


class MemoryRepository(Protocol):
    """记忆记录的读写接口。"""

    async def add(self, record: MemoryRecord) -> MemoryRecord: ...


class SignalRepository(Protocol):
    """指标和特征快照的时序写入接口。"""

    async def write(self, snapshot: SignalSnapshot) -> None: ...


class CandleRepository(Protocol):
    """K 线数据的时序写入接口。"""

    async def write(self, candle: Candle) -> None: ...
    async def write_batch(self, candles: Sequence[Candle]) -> None: ...
    async def query_history(
        self,
        *,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 5000,
    ) -> Sequence[dict[str, Any]]: ...


class SourcePriorityRepository(Protocol):
    """路由优先级配置仓储接口。"""

    async def get(self, route_key: DataRouteKey) -> Any | None: ...
    async def upsert(
        self,
        route_key: DataRouteKey,
        *,
        priorities: list[str],
        enabled: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> Any: ...
    async def reorder(self, route_key: DataRouteKey, *, priorities: list[str]) -> None: ...


class KlineSyncStateRepository(Protocol):
    """K 线同步状态仓储接口。"""

    async def get(self, symbol: str, market: ExchangeKind, interval: str) -> Any | None: ...
    async def get_or_create(self, symbol: str, market: ExchangeKind, interval: str) -> Any: ...
    async def update(self, state: Any) -> None: ...


class UnitOfWork(Protocol):
    """把一次业务操作涉及的多仓储写入收敛到同一个事务边界。"""

    task_runs: TaskRunRepository
    task_events: TaskEventRepository
    task_artifacts: TaskArtifactRepository
    news: NewsRepository
    basic_infos: BasicInfoRepository
    candidates: CandidateRepository
    positions: PositionRepository
    memories: MemoryRepository
    signals: SignalRepository
    candles: CandleRepository
    source_priorities: SourcePriorityRepository
    kline_sync_states: KlineSyncStateRepository

    async def __aenter__(self) -> UnitOfWork: ...
    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
