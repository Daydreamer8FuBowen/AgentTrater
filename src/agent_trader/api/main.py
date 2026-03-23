from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorDatabase

from agent_trader.api.routes.admin_tables import router as admin_tables_router
from agent_trader.application.services.data_source_gateway import DataSourceRegistry
from agent_trader.api.routes.health import router as health_router
from agent_trader.api.routes.triggers import router as trigger_router
from agent_trader.core.config import get_settings
from agent_trader.ingestion.models import DataRouteKey
from agent_trader.core.logging import configure_logging
from agent_trader.ingestion.sources.baostock_source import BaoStockSource
from agent_trader.ingestion.sources.tushare_source import TuShareSource
from agent_trader.storage.mongo.repository import MongoSourcePriorityRepository
from agent_trader.storage.connection_manager import AppConnectionManager

logger = logging.getLogger(__name__)


def _build_source_registry() -> DataSourceRegistry:
    """按配置构建统一数据源注册表。"""
    settings = get_settings()
    registry = DataSourceRegistry()

    # BaoStock 使用公开账号也可用，默认总是注册。
    registry.register(BaoStockSource.from_settings(settings))

    # TuShare 依赖 token，仅在显式配置时注册。
    if settings.tushare.token:
        registry.register(TuShareSource.from_settings(settings))
    else:
        logger.info("TUSHARE_TOKEN 未设置，跳过 TuShareSource 注册")

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
        await _rebuild_default_source_priorities(connections.mongo_manager.database, source_registry)
    else:
        logger.info("数据路由引导已禁用（由 DATA_ROUTING_ENABLED 控制）")

    try:
        yield
    finally:
        await connections.close()


def create_app() -> FastAPI:
    """创建 FastAPI 应用并挂载统一路由。"""

    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(trigger_router, prefix="/api/v1")
    app.include_router(admin_tables_router, prefix="/api/v1")
    return app


app = create_app()