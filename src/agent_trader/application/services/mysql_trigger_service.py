from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from agent_trader.storage.base import CandleRepository, CandidateRepository, MemoryRepository, SignalRepository, UnitOfWork
from agent_trader.storage.mysql.repository import MySQLOpportunityRepository, MySQLResearchTaskRepository


class _UnsupportedCandidateRepository:
    async def upsert(self, candidate: object) -> object:
        raise NotImplementedError("MySQL candidate repository 尚未实现")

    async def list_active(self) -> list[object]:
        raise NotImplementedError("MySQL candidate repository 尚未实现")


class _UnsupportedMemoryRepository:
    async def add(self, record: object) -> object:
        raise NotImplementedError("MySQL memory repository 尚未实现")


class _UnsupportedSignalRepository:
    async def write(self, snapshot: object) -> None:
        raise NotImplementedError("Signal snapshot 当前由时序库存储，不落 MySQL")


class _UnsupportedCandleRepository:
    async def write(self, candle: object) -> None:
        raise NotImplementedError("Candle 当前由 InfluxDB 存储，不落 MySQL")

    async def write_batch(self, candles: list[object]) -> None:
        raise NotImplementedError("Candle 当前由 InfluxDB 存储，不落 MySQL")


class MySQLUnitOfWork(UnitOfWork):
    """基于 `AsyncSession` 的 MySQL 工作单元。

    设计重点：
    - 把 `opportunities` 和 `research_tasks` 写入收敛到同一个事务边界。
    - 对当前未落 MySQL 的仓储明确给出 `NotImplementedError`，避免静默成功。
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.opportunities = MySQLOpportunityRepository(session)
        self.research_tasks = MySQLResearchTaskRepository(session)
        self.candidates: CandidateRepository = _UnsupportedCandidateRepository()
        self.memories: MemoryRepository = _UnsupportedMemoryRepository()
        self.signals: SignalRepository = _UnsupportedSignalRepository()
        self.candles: CandleRepository = _UnsupportedCandleRepository()

    async def __aenter__(self) -> UnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if exc_type is not None:
            await self.rollback()
            return
        await self.commit()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


# 备注：
# 这里没有复制 `TriggerService` 逻辑，而是只提供 MySQL 持久化所需的 `UnitOfWork`。
# 现有的 `application/services/trigger_service.py` 已经依赖 `UnitOfWork` 协议，
# 因此在依赖注入层把 InMemoryUnitOfWork 替换为 MySQLUnitOfWork 即可完成接入。
