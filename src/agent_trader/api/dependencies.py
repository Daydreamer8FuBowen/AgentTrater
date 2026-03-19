from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import Depends

from agent_trader.agents.graphs.trigger_router import TriggerRouterGraph
from agent_trader.application.services.trigger_service import TriggerService
from agent_trader.core.config import Settings, get_settings
from agent_trader.ingestion.sources.tushare_source import TuShareSource
from agent_trader.storage.base import CandleRepository, CandidateRepository, MemoryRepository, OpportunityRepository, ResearchTaskRepository, SignalRepository, UnitOfWork
from agent_trader.storage.mysql import MySQLUnitOfWork, MySQLConnectionManager


class InMemoryOpportunityRepository:
    def __init__(self) -> None:
        self.items: list[Any] = []

    async def add(self, opportunity: Any) -> Any:
        self.items.append(opportunity)
        return opportunity


class InMemoryResearchTaskRepository:
    def __init__(self) -> None:
        self.items: list[Any] = []

    async def add(self, task: Any) -> Any:
        self.items.append(task)
        return task


class InMemoryCandidateRepository:
    def __init__(self) -> None:
        self.items: list[Any] = []

    async def upsert(self, candidate: Any) -> Any:
        self.items.append(candidate)
        return candidate

    async def list_active(self) -> list[Any]:
        return self.items


class InMemoryMemoryRepository:
    def __init__(self) -> None:
        self.items: list[Any] = []

    async def add(self, record: Any) -> Any:
        self.items.append(record)
        return record


class InMemorySignalRepository:
    async def write(self, snapshot: Any) -> None:
        return None


class InMemoryCandleRepository:
    def __init__(self) -> None:
        self.items: list[Any] = []

    async def write(self, candle: Any) -> None:
        self.items.append(candle)

    async def write_batch(self, candles: list[Any]) -> None:
        self.items.extend(candles)



# MySQL事务实现：
async def get_uow(settings: Settings = Depends(get_settings)) -> AsyncIterator[UnitOfWork]:
    """
    获取 MySQLUnitOfWork，注入真实数据库事务。
    """
    mysql_manager = MySQLConnectionManager(settings.mysql)
    async with mysql_manager.session() as session:
        yield MySQLUnitOfWork(session)





def get_tushare_source(settings: Settings = Depends(get_settings)) -> TuShareSource:
    """
    获取 TuShareSource 依赖。

    从统一配置系统中读取 token 和 http_url，创建 TuShareSource 实例。
    如果 token 为空，将抛出 ValueError。
    """
    if not settings.tushare.token:
        # 如果没有 token，返回一个空的 stub，避免启动失败
        return None  # type: ignore

    return TuShareSource.from_settings(settings)


def get_trigger_service(
    settings: Settings = Depends(get_settings),
    unit_of_work: UnitOfWork = Depends(get_uow),
) -> TriggerService:
    del settings
    return TriggerService(unit_of_work=unit_of_work, router_graph=TriggerRouterGraph())