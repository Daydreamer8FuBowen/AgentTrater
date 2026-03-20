from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from agent_trader.agents.graphs.trigger_router import TriggerRouterGraph
from agent_trader.application.services.table_admin_service import TableAdminService
from agent_trader.application.services.trigger_service import TriggerService
from agent_trader.core.config import Settings, get_settings
from agent_trader.ingestion.sources.tushare_source import TuShareSource
from agent_trader.storage.base import UnitOfWork
from agent_trader.storage.mongo import MongoConnectionManager, MongoUnitOfWork


def get_mongo_manager(request: Request) -> MongoConnectionManager:
    return request.app.state.mongo_manager


def get_mongo_database(
    manager: MongoConnectionManager = Depends(get_mongo_manager),
) -> AsyncIOMotorDatabase:
    return manager.database


async def get_uow(
    database: AsyncIOMotorDatabase = Depends(get_mongo_database),
) -> AsyncIterator[UnitOfWork]:
    yield MongoUnitOfWork(database)


async def get_table_admin_service(
    database: AsyncIOMotorDatabase = Depends(get_mongo_database),
) -> AsyncIterator[TableAdminService]:
    yield TableAdminService(database)


def get_tushare_source(settings: Settings = Depends(get_settings)) -> TuShareSource:
    """
    获取 TuShareSource 依赖。

    从统一配置系统中读取 token 和 http_url，创建 TuShareSource 实例。
    如果 token 为空，将抛出 ValueError。
    """
    if not settings.tushare.token:
        return None  # type: ignore

    return TuShareSource.from_settings(settings)


def get_trigger_service(
    settings: Settings = Depends(get_settings),
    unit_of_work: UnitOfWork = Depends(get_uow),
) -> TriggerService:
    del settings
    return TriggerService(unit_of_work=unit_of_work, router_graph=TriggerRouterGraph())