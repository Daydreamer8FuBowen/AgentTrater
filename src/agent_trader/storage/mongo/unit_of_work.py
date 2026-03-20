from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from agent_trader.storage.base import CandleRepository, CandidateRepository, MemoryRepository, SignalRepository, UnitOfWork
from agent_trader.storage.mongo.repository import MongoTaskArtifactRepository, MongoTaskEventRepository, MongoTaskRunRepository


class _UnsupportedCandidateRepository:
    async def upsert(self, candidate: object) -> object:
        raise NotImplementedError("Candidate repository 尚未接入 Mongo 运行模型")

    async def list_active(self) -> list[object]:
        raise NotImplementedError("Candidate repository 尚未接入 Mongo 运行模型")


class _UnsupportedMemoryRepository:
    async def add(self, record: object) -> object:
        raise NotImplementedError("Memory repository 尚未接入 Mongo 运行模型")


class _UnsupportedSignalRepository:
    async def write(self, snapshot: object) -> None:
        raise NotImplementedError("Signal snapshot 当前由 InfluxDB 存储")


class _UnsupportedCandleRepository:
    async def write(self, candle: object) -> None:
        raise NotImplementedError("Candle 当前由 InfluxDB 存储")

    async def write_batch(self, candles: list[object]) -> None:
        raise NotImplementedError("Candle 当前由 InfluxDB 存储")


class MongoUnitOfWork(UnitOfWork):
    """MongoDB 工作单元。"""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.task_runs = MongoTaskRunRepository(database)
        self.task_events = MongoTaskEventRepository(database)
        self.task_artifacts = MongoTaskArtifactRepository(database)
        self.candidates: CandidateRepository = _UnsupportedCandidateRepository()
        self.memories: MemoryRepository = _UnsupportedMemoryRepository()
        self.signals: SignalRepository = _UnsupportedSignalRepository()
        self.candles: CandleRepository = _UnsupportedCandleRepository()

    async def __aenter__(self) -> UnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        del exc, tb
        if exc_type is None:
            await self.commit()
            return
        await self.rollback()

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None