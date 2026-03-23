"""Mongo 实现的 UnitOfWork 聚合入口。

该模块将任务相关的 Mongo 仓库聚合为一个工作单元对象，方便在服务中以 `async with` 方式使用。
注意：部分存储（如 candles、signals）当前由其它后端（InfluxDB）负责，因此在 Mongo 实现中标记为未支持。
"""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from agent_trader.storage.base import (
    CandleRepository,
    CandidateRepository,
    MemoryRepository,
    NewsRepository,
    SignalRepository,
    SourcePriorityRepository,
    UnitOfWork,
)
from agent_trader.storage.mongo.repository import (
    MongoNewsRepository,
    MongoSourcePriorityRepository,
    MongoTaskArtifactRepository,
    MongoTaskEventRepository,
    MongoTaskRunRepository,
)


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
    """MongoDB 工作单元。

    用法示例：

    ```py
    async with MongoUnitOfWork(db) as uow:
        await uow.task_runs.add(...)
        # commit 会在 __aexit__ 中被调用（当前为 no-op）
    ```
    """

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        # 已支持的仓库
        self.task_runs = MongoTaskRunRepository(database)
        self.task_events = MongoTaskEventRepository(database)
        self.task_artifacts = MongoTaskArtifactRepository(database)
        self.news: NewsRepository = MongoNewsRepository(database)
        self.source_priorities: SourcePriorityRepository = MongoSourcePriorityRepository(database)
        # 尚未接入 Mongo 的仓库（占位）
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
        """提交操作（当前为 no-op，保留扩展点）。"""
        return None

    async def rollback(self) -> None:
        """回滚操作（当前为 no-op，保留扩展点）。"""
        return None