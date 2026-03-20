from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent_trader.api.routes.admin_tables import router as admin_tables_router
from agent_trader.api.routes.health import router as health_router
from agent_trader.api.routes.triggers import router as trigger_router
from agent_trader.core.config import get_settings
from agent_trader.core.logging import configure_logging
from agent_trader.storage.mongo import MongoConnectionManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 所有进程级初始化放到 lifespan 中，后续接数据库、缓存、调度器也沿用这个入口。
    settings = get_settings()
    configure_logging(settings.log_level)
    mongo_manager = MongoConnectionManager(settings.mongo)
    try:
        await mongo_manager.ping()
        await mongo_manager.ensure_indexes()
    except Exception:
        # 测试和本地调试场景下允许应用先启动，等 Mongo 可用后再访问相关接口。
        pass
    app.state.mongo_manager = mongo_manager
    try:
        yield
    finally:
        await mongo_manager.close()


def create_app() -> FastAPI:
    """创建 FastAPI 应用并挂载统一路由。"""

    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(trigger_router, prefix="/api/v1")
    app.include_router(admin_tables_router, prefix="/api/v1")
    return app


app = create_app()