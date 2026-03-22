from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from agent_trader.api.routes.admin_tables import router as admin_tables_router
from agent_trader.application.services.data_source_gateway import DataSourceRegistry
from agent_trader.api.routes.health import router as health_router
from agent_trader.api.routes.triggers import router as trigger_router
from agent_trader.core.config import get_settings
from agent_trader.core.logging import configure_logging
from agent_trader.ingestion.sources.baostock_source import BaoStockSource
from agent_trader.ingestion.sources.tushare_source import TuShareSource
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 所有进程级初始化放到 lifespan 中，后续接数据库、缓存等资源都沿用这个入口。
    settings = get_settings()
    configure_logging(settings.log_level)
    connections = AppConnectionManager.from_settings(settings)
    await connections.start()

    app.state.connections = connections
    app.state.mongo_manager = connections.mongo_manager
    app.state.influx_manager = connections.influx_manager
    app.state.source_registry = _build_source_registry()

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