from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorDatabase

from agent_trader.api.routes.charts import router as charts_router
from agent_trader.api.routes.data import router as data_router
from agent_trader.api.routes.data_sources import router as data_sources_router
from agent_trader.api.routes.health import router as health_router
from agent_trader.api.routes.symbols import router as symbols_router
from agent_trader.application.data_access.gateway import (
    DataAccessGateway,
    DataSourceRegistry,
    SourceSelectionAdapter,
)
from agent_trader.application.services.basic_info_aggregation_service import (
    BasicInfoAggregationService,
)
from agent_trader.core.config import get_settings
from agent_trader.core.logging import configure_logging
from agent_trader.ingestion.models import DataRouteKey
from agent_trader.ingestion.sources.baostock_source import BaoStockSource
from agent_trader.ingestion.sources.tushare_source import TuShareSource
from agent_trader.storage.connection_manager import AppConnectionManager
from agent_trader.storage.mongo import MongoUnitOfWork
from agent_trader.storage.mongo.documents import BasicInfoDocument
from agent_trader.storage.mongo.repository import MongoSourcePriorityRepository

logger = logging.getLogger(__name__)


def _build_source_registry() -> DataSourceRegistry:
    """按配置构建统一数据源注册表。"""
    settings = get_settings()
    registry = DataSourceRegistry()

    # TuShare 依赖 token，仅在显式配置时注册；若可用则置于优先级链首位。
    if settings.tushare.token:
        registry.register(TuShareSource.from_settings(settings))
    else:
        logger.info("TUSHARE_TOKEN 未设置，跳过 TuShareSource 注册")

    # BaoStock 使用公开账号也可用，默认总是注册（通常作为回退源）。
    registry.register(BaoStockSource.from_settings(settings))

    return registry


async def _rebuild_default_source_priorities(
    database: AsyncIOMotorDatabase,
    registry: DataSourceRegistry,
) -> None:
    """按当前注册源能力补齐默认路由优先级（按注册顺序）。

    仅为不存在的 route_id 新增记录，不覆盖已有配置。
    """

    route_to_sources: dict[DataRouteKey, list[str]] = {}
    for source_name in registry.names():
        provider = registry.get(source_name)
        if provider is None:
            continue

        capabilities = getattr(provider, "capabilities", None)
        if not callable(capabilities):
            continue

        for spec in capabilities():
            markets = spec.markets or (None,)
            intervals = spec.intervals or (None,)
            for market in markets:
                for interval in intervals:
                    route_key = DataRouteKey(
                        capability=spec.capability,
                        market=market,
                        interval=interval,
                    )
                    sources = route_to_sources.setdefault(route_key, [])
                    if source_name not in sources:
                        sources.append(source_name)

    priority_repo = MongoSourcePriorityRepository(database)
    inserted_count = 0
    skipped_count = 0
    for route_key, priorities in route_to_sources.items():
        existing_route = await priority_repo.get(route_key)
        if existing_route is not None:
            skipped_count += 1
            continue

        await priority_repo.upsert(
            route_key,
            priorities=priorities,
            enabled=True,
            metadata={"bootstrap": True},
        )
        inserted_count += 1

    logger.info(
        "数据源优先级引导完成，计算路由数=%d，新增=%d，跳过已有=%d",
        len(route_to_sources),
        inserted_count,
        skipped_count,
    )


def _build_basic_info_aggregation_service(
    database: AsyncIOMotorDatabase,
    registry: DataSourceRegistry,
) -> BasicInfoAggregationService:
    selector = SourceSelectionAdapter(
        registry=registry,
        priority_repository=MongoSourcePriorityRepository(database),
    )
    gateway = DataAccessGateway(selector)
    return BasicInfoAggregationService(
        gateway=gateway,
        uow_factory=lambda: MongoUnitOfWork(database),
    )


async def _bootstrap_basic_info_symbols_if_empty(
    database: AsyncIOMotorDatabase,
    registry: DataSourceRegistry,
) -> None:
    """仅在 basic_infos 为空时执行全量 symbol 初始化。"""

    existing = await database[BasicInfoDocument.collection_name].find_one({}, {"_id": 1})
    if existing is not None:
        logger.info(
            "basic_info symbol 引导跳过：集合 %s 已存在数据", BasicInfoDocument.collection_name
        )
        return

    try:
        service = _build_basic_info_aggregation_service(database, registry)
        summary = await service.sync_basic_info_snapshot()
        logger.info(
            "basic_info symbol 引导完成，请求源数=%d，输入记录=%d，去重后=%d，新增=%d",
            summary.get("requested_sources", 0),
            summary.get("input_count", 0),
            summary.get("dedup_count", 0),
            summary.get("persisted", {}).get("upserted", 0),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("basic_info symbol 引导失败：%s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 所有进程级初始化放到 lifespan 中，后续接数据库、缓存等资源都沿用这个入口。
    settings = get_settings()
    configure_logging(settings.log_level)
    connections = AppConnectionManager.from_settings(settings)
    await connections.start()

    source_registry = _build_source_registry()

    app.state.connections = connections
    app.state.mongo_manager = connections.mongo_manager
    app.state.influx_manager = connections.influx_manager
    app.state.source_registry = source_registry

    if settings.data_routing.enabled:
        await _rebuild_default_source_priorities(
            connections.mongo_manager.database, source_registry
        )
    else:
        logger.info("数据路由引导已禁用（由 DATA_ROUTING_ENABLED 控制）")

    await _bootstrap_basic_info_symbols_if_empty(
        connections.mongo_manager.database, source_registry
    )

    try:
        yield
    finally:
        await connections.close()


def create_app() -> FastAPI:
    """创建 FastAPI 应用并挂载统一路由。"""

    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(data_router, prefix="/api/v1")
    app.include_router(data_sources_router, prefix="/api/v1")
    app.include_router(symbols_router, prefix="/api/v1")
    app.include_router(charts_router, prefix="/api/v1")
    return app


app = create_app()
