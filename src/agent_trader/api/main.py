from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent_trader.api.routes.health import router as health_router
from agent_trader.api.routes.triggers import router as trigger_router
from agent_trader.core.config import get_settings
from agent_trader.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 所有进程级初始化放到 lifespan 中，后续接数据库、缓存、调度器也沿用这个入口。
    settings = get_settings()
    configure_logging(settings.log_level)
    yield


def create_app() -> FastAPI:
    """创建 FastAPI 应用并挂载统一路由。"""

    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(trigger_router, prefix="/api/v1")
    return app


app = create_app()