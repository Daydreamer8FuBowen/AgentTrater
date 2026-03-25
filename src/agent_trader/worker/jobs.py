from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from agent_trader.application.services.kline_sync_service import KlineSyncService
from agent_trader.core.config import Settings, get_settings

_A_SHARE_MORNING_SESSION = (time(9, 30), time(11, 30))
_A_SHARE_AFTERNOON_SESSION = (time(13, 0), time(15, 0))
_BACKFILL_CHECK_INTERVAL_MINUTES = 1


def register_kline_sync_jobs(
    scheduler: AsyncIOScheduler,
    *,
    service_factory: Callable[[], KlineSyncService],
    settings: Settings | None = None,
) -> None:
    current_settings = settings or get_settings()
    sync_config = current_settings.kline_sync

    for market in sync_config.enabled_markets:
        scheduler.add_job(
            _run_realtime_positions,
            "interval",
            seconds=sync_config.realtime_m5_interval_seconds,
            kwargs={"service_factory": service_factory, "market": market},
            id=f"realtime_m5_positions_{market}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.add_job(
            _run_realtime_candidates,
            "interval",
            seconds=sync_config.realtime_m5_interval_seconds,
            kwargs={"service_factory": service_factory, "market": market},
            id=f"realtime_m5_candidates_{market}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.add_job(
            _run_daily_d1,
            "cron",
            hour=sync_config.d1_sync_hour,
            minute=0,
            kwargs={"service_factory": service_factory, "market": market},
            id=f"daily_d1_all_{market}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.add_job(
            _run_backfill_d1,
            "interval",
            minutes=_BACKFILL_CHECK_INTERVAL_MINUTES,
            kwargs={"service_factory": service_factory, "market": market},
            id=f"backfill_d1_all_{market}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.add_job(
            _run_backfill_m5,
            "interval",
            minutes=_BACKFILL_CHECK_INTERVAL_MINUTES,
            kwargs={"service_factory": service_factory, "market": market},
            id=f"backfill_m5_positions_candidates_{market}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )


async def _run_realtime_positions(*, service_factory: Callable[[], KlineSyncService], market: str) -> None:
    if not _should_run_realtime(market):
        return
    await service_factory().sync_realtime_m5_positions(market)


async def _run_realtime_candidates(*, service_factory: Callable[[], KlineSyncService], market: str) -> None:
    if not _should_run_realtime(market):
        return
    await service_factory().sync_realtime_m5_candidates(market)


async def _run_daily_d1(*, service_factory: Callable[[], KlineSyncService], market: str) -> None:
    await service_factory().sync_daily_d1_all(market)


async def _run_backfill_d1(*, service_factory: Callable[[], KlineSyncService], market: str) -> None:
    if not _should_run_backfill(market):
        return
    await service_factory().sync_backfill_d1_all(market)


async def _run_backfill_m5(*, service_factory: Callable[[], KlineSyncService], market: str) -> None:
    if not _should_run_backfill(market):
        return
    await service_factory().sync_backfill_m5_positions_candidates(market)


def _should_run_realtime(market: str, now: datetime | None = None) -> bool:
    """实时任务仅在市场交易时段触发。"""
    now_value = now or datetime.now()
    return _is_market_trading_time(market, now_value)


def _should_run_backfill(market: str, now: datetime | None = None) -> bool:
    """回补任务仅在市场非交易时段触发。"""
    now_value = now or datetime.now()
    return not _is_market_trading_time(market, now_value)


def _is_market_trading_time(market: str, now: datetime) -> bool:
    """判断给定市场在当前时间是否处于交易时段。"""
    normalized_market = market.strip().lower()
    if normalized_market in {"sse", "sh", "szse", "sz"}:
        if now.weekday() >= 5:
            return False
        current = now.time()
        morning_start, morning_end = _A_SHARE_MORNING_SESSION
        afternoon_start, afternoon_end = _A_SHARE_AFTERNOON_SESSION
        in_morning = morning_start <= current <= morning_end
        in_afternoon = afternoon_start <= current <= afternoon_end
        return in_morning or in_afternoon
    return True
