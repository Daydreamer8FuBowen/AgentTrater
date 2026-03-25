from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import signal

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from agent_trader.application.data_access import DataSourceRegistry
from agent_trader.core.config import Settings, get_settings
from agent_trader.core.logging import configure_logging
from agent_trader.ingestion.sources import BaoStockSource, TuShareSource
from agent_trader.storage.connection_manager import AppConnectionManager
from agent_trader.worker.factory import build_kline_sync_service_factory, create_scheduler
from agent_trader.worker.jobs import register_kline_sync_jobs

logger = logging.getLogger(__name__)


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

    registry.register(BaoStockSource.from_settings(settings))
    if settings.tushare.token:
        registry.register(TuShareSource.from_settings(settings))
    else:
        logger.info("TUSHARE_TOKEN 未设置，worker 跳过 TuShareSource 注册")

    return registry


async def bootstrap_worker(settings: Settings | None = None) -> WorkerRuntime:
    """启动 worker：连接就绪后自动注册并启动 K 线同步任务。"""
    current_settings = settings or get_settings()
    configure_logging(current_settings.log_level)

    connections = AppConnectionManager.from_settings(current_settings)
    await connections.start()

    try:
        source_registry = _build_source_registry(current_settings)
        scheduler = create_scheduler(current_settings)
        service_factory = build_kline_sync_service_factory(
            database=connections.mongo_manager.database,
            influx_manager=connections.influx_manager,
            source_registry=source_registry,
            settings=current_settings,
        )
        register_kline_sync_jobs(
            scheduler,
            service_factory=service_factory,
            settings=current_settings,
        )
        scheduler.start()
        logger.info(
            "worker scheduler started: markets=%s, jobs=%d",
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
