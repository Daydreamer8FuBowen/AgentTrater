from __future__ import annotations

import asyncio
import logging
import signal
from dataclasses import dataclass

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from agent_trader.application.data_access import DataSourceRegistry
from agent_trader.application.data_access.gateway import SourceSelectionAdapter
from agent_trader.core.config import Settings, get_settings
from agent_trader.core.logging import configure_logging
from agent_trader.ingestion.sources import BaoStockSource, TuShareSource
from agent_trader.storage.connection_manager import AppConnectionManager
from agent_trader.storage.mongo.repository import MongoSourcePriorityRepository
from agent_trader.worker.factory import (
    build_kline_sync_service_factory,
    build_company_detail_sync_service_factory,
    create_scheduler,
)
from agent_trader.worker.jobs import register_kline_sync_jobs, register_company_detail_sync_jobs

logger = logging.getLogger(__name__)


async def _health_check_sources(selector: SourceSelectionAdapter) -> None:
    """启动前快速检查连通性，借由 SourceSelectionAdapter 的机制自动淘汰无效数据源到队尾。"""
    from datetime import timedelta

    from agent_trader.application.data_access.gateway import DataCapability, DataRouteKey
    from agent_trader.core.time import utc_now
    from agent_trader.domain.models import BarInterval, ExchangeKind
    from agent_trader.ingestion.models import KlineQuery

    logger.info("开始执行数据源连通性检查...")
    now = utc_now()
    # 用上证指数或大盘代表票做连通性心跳探测
    query = KlineQuery(
        symbol="000001.SZ",
        start_time=now - timedelta(days=10),
        end_time=now,
        interval=BarInterval.D1,
        market=ExchangeKind.SZSE,
    )

    route_key = DataRouteKey(
        capability=DataCapability.KLINE,
        market=ExchangeKind.SZSE,
        interval=BarInterval.D1,
    )

    async def _invoke(source_name: str, provider: object):
        if not hasattr(provider, "fetch_klines_unified"):
            raise RuntimeError(f"Source {source_name} does not support fetch_klines_unified")
        result = await provider.fetch_klines_unified(query)
        if hasattr(result, "metadata") and result.metadata and "error" in result.metadata:
            raise RuntimeError(f"Source {source_name} error: {result.metadata['error']}")
        return source_name, result

    try:
        source_name, result = await selector.execute(route_key, _invoke)
        if result.payload:
            logger.info(
                "数据源 %s 健康检查成功 (获取到 %d 条样例数据)", source_name, len(result.payload)
            )
        else:
            logger.warning("数据源 %s 健康检查通过，但数据为空 (可能非交易日)", source_name)
    except Exception:
        logger.exception("所有数据源健康检查均失败！")


@dataclass(slots=True)
class WorkerRuntime:
    """后台 worker 运行时资源句柄。"""

    connections: AppConnectionManager
    scheduler: AsyncIOScheduler

    async def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        await self.connections.close()


def _register_shutdown_signals(shutdown_event: asyncio.Event) -> None:
    """注册进程退出信号，触发 worker 优雅关闭。"""
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown_event.set)
        except (NotImplementedError, RuntimeError):
            continue


def _build_source_registry(settings: Settings) -> DataSourceRegistry:
    """按配置构建 worker 侧数据源注册表。"""
    registry = DataSourceRegistry()

    if settings.tushare.token:
        registry.register(TuShareSource.from_settings(settings))
    else:
        logger.info("TUSHARE_TOKEN 未设置，worker 跳过 TuShareSource 注册")

    registry.register(BaoStockSource.from_settings(settings))

    return registry


async def bootstrap_worker(settings: Settings | None = None) -> WorkerRuntime:
    """启动 worker：连接就绪后自动注册并启动 K 线同步任务。"""
    current_settings = settings or get_settings()
    configure_logging(current_settings.log_level)

    connections = AppConnectionManager.from_settings(current_settings)
    await connections.start()

    try:
        source_registry = _build_source_registry(current_settings)

        # 使用 SourceSelectionAdapter 进行健康检查，自动汰劣留良
        selector = SourceSelectionAdapter(
            registry=source_registry,
            priority_repository=MongoSourcePriorityRepository(connections.mongo_manager.database),
        )
        await _health_check_sources(selector)

        scheduler = create_scheduler(current_settings)
        kline_service_factory = build_kline_sync_service_factory(
            database=connections.mongo_manager.database,
            influx_manager=connections.influx_manager,
            source_registry=source_registry,
            settings=current_settings,
        )
        register_kline_sync_jobs(
            scheduler,
            service_factory=kline_service_factory,
            settings=current_settings,
        )

        company_detail_service_factory = build_company_detail_sync_service_factory(
            database=connections.mongo_manager.database,
            source_registry=source_registry,
        )
        register_company_detail_sync_jobs(
            scheduler,
            service_factory=company_detail_service_factory,
            settings=current_settings,
        )

        scheduler.start()
        logger.info(
            "调度器已启动：市场=%s，任务数=%d",
            ",".join(current_settings.kline_sync.enabled_markets),
            len(scheduler.get_jobs()),
        )
        return WorkerRuntime(connections=connections, scheduler=scheduler)
    except Exception:  # noqa: BLE001
        await connections.close()
        raise


async def run_worker_forever(
    settings: Settings | None = None,
    *,
    shutdown_event: asyncio.Event | None = None,
    register_signals: bool = True,
) -> None:
    """启动 worker 并持续运行，直到接收到退出信号。"""
    runtime = await bootstrap_worker(settings=settings)
    stop_event = shutdown_event or asyncio.Event()

    if register_signals:
        _register_shutdown_signals(stop_event)

    try:
        await stop_event.wait()
    finally:
        await runtime.stop()


def main() -> None:
    """worker 进程入口（可由 `python -m agent_trader.worker` 触发）。"""
    try:
        asyncio.run(run_worker_forever())
    except KeyboardInterrupt:
        pass
