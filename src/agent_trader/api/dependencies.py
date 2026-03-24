from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from agent_trader.application.data_access.gateway import (
    DataAccessGateway,
    DataSourceRegistry,
    SourceSelectionAdapter,
)
from agent_trader.application.services.basic_info_aggregation_service import BasicInfoAggregationService
from agent_trader.core.config import Settings, get_settings
from agent_trader.ingestion.sources.baostock_source import BaoStockSource
from agent_trader.ingestion.sources.tushare_source import TuShareSource
from agent_trader.storage.base import SourcePriorityRepository, UnitOfWork
from agent_trader.storage.influx import InfluxConnectionManager
from agent_trader.storage.mongo import MongoConnectionManager, MongoUnitOfWork


def get_mongo_manager(request: Request) -> MongoConnectionManager:
    return request.app.state.mongo_manager


def get_mongo_database(
    manager: MongoConnectionManager = Depends(get_mongo_manager),
) -> AsyncIOMotorDatabase:
    return manager.database


def get_influx_manager(request: Request) -> InfluxConnectionManager:
    return request.app.state.influx_manager


async def get_uow(
    database: AsyncIOMotorDatabase = Depends(get_mongo_database),
) -> AsyncIterator[UnitOfWork]:
    yield MongoUnitOfWork(database)


def get_tushare_source(settings: Settings = Depends(get_settings)) -> TuShareSource:
    """
    获取 TuShareSource 依赖。

    从统一配置系统中读取 token 和 http_url，创建 TuShareSource 实例。
    如果 token 为空，将抛出 ValueError。
    """
    if not settings.tushare.token:
        return None  # type: ignore

    return TuShareSource.from_settings(settings)


def get_baostock_source(settings: Settings = Depends(get_settings)) -> BaoStockSource:
    """获取 BaoStockSource 依赖。"""
    return BaoStockSource.from_settings(settings)


def get_source_registry(request: Request) -> DataSourceRegistry:
    registry = getattr(request.app.state, "source_registry", None)
    if registry is None:
        registry = DataSourceRegistry()
        request.app.state.source_registry = registry
    return registry


def get_source_priority_repository(
    unit_of_work: UnitOfWork = Depends(get_uow),
) -> SourcePriorityRepository:
    return unit_of_work.source_priorities


def get_source_selection_adapter(
    registry: DataSourceRegistry = Depends(get_source_registry),
    priority_repository: SourcePriorityRepository = Depends(get_source_priority_repository),
) -> SourceSelectionAdapter:
    return SourceSelectionAdapter(
        registry=registry,
        priority_repository=priority_repository,
    )


def get_data_access_gateway(
    selector: SourceSelectionAdapter = Depends(get_source_selection_adapter),
) -> DataAccessGateway:
    return DataAccessGateway(selector)


def get_basic_info_aggregation_service(
    gateway: DataAccessGateway = Depends(get_data_access_gateway),
    database: AsyncIOMotorDatabase = Depends(get_mongo_database),
) -> BasicInfoAggregationService:
    return BasicInfoAggregationService(
        gateway=gateway,
        uow_factory=lambda: MongoUnitOfWork(database),
    )
