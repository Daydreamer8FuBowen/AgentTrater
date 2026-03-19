from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from agent_trader.domain.models import Candle, Candidate, MemoryRecord, Opportunity, ResearchTask, SignalSnapshot


class OpportunityRepository(Protocol):
    """结构化机会对象的持久化接口。"""

    async def add(self, opportunity: Opportunity) -> Opportunity: ...


class ResearchTaskRepository(Protocol):
    """研究任务仓储接口。"""

    async def add(self, task: ResearchTask) -> ResearchTask: ...


class CandidateRepository(Protocol):
    """候选池查询与写入接口。"""

    async def upsert(self, candidate: Candidate) -> Candidate: ...
    async def list_active(self) -> Sequence[Candidate]: ...


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


class UnitOfWork(Protocol):
    """把一次业务操作涉及的多仓储写入收敛到同一个事务边界。"""

    opportunities: OpportunityRepository
    research_tasks: ResearchTaskRepository
    candidates: CandidateRepository
    memories: MemoryRepository
    signals: SignalRepository
    candles: CandleRepository

    async def __aenter__(self) -> UnitOfWork: ...
    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...