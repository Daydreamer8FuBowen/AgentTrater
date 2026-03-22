from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

# 定时器
def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    return scheduler


def register_data_source_routing_jobs(
    scheduler: AsyncIOScheduler,
    *,
    health_check_interval_seconds: int,
    rebalance_interval_seconds: int,
    run_health_check: Callable[[], Awaitable[int]],
    run_rebalance: Callable[[], Awaitable[None]],
) -> None:
    """注册统一数据源路由维护任务。"""

    async def _health_check_job() -> None:
        checked = await run_health_check()
        logger.info("data source routing health check finished count=%s", checked)

    async def _rebalance_job() -> None:
        await run_rebalance()
        logger.info("data source routing rebalance finished")

    scheduler.add_job(
        _health_check_job,
        trigger="interval",
        seconds=max(1, health_check_interval_seconds),
        id="data_source_routing_health_check",
        replace_existing=True,
    )
    scheduler.add_job(
        _rebalance_job,
        trigger="interval",
        seconds=max(1, rebalance_interval_seconds),
        id="data_source_routing_rebalance",
        replace_existing=True,
    )