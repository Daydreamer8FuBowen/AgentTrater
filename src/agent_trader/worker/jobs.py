from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from agent_trader.application.jobs.kline_sync import KlineSyncService
from agent_trader.application.jobs.company_detail_sync import CompanyDetailSyncService
from agent_trader.core.config import Settings, get_settings
from agent_trader.domain.models import ExchangeKind

logger = logging.getLogger(__name__)
_HISTORY_UPDATE_HOUR = 23
_HISTORY_UPDATE_MINUTE = 0


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
            _run_market_history_update,
            "date",
            run_date=datetime.now(timezone.utc),
            kwargs={"service_factory": service_factory, "market": market},
            id=f"kline_history_update_startup_{market}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.add_job(
            _run_market_history_update,
            "cron",
            hour=_HISTORY_UPDATE_HOUR,
            minute=_HISTORY_UPDATE_MINUTE,
            kwargs={"service_factory": service_factory, "market": market},
            id=f"kline_history_update_daily_{market}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )


async def _run_market_history_update(
    *, service_factory: Callable[[], KlineSyncService], market: str
) -> None:
    logger.info("触发市场K线历史更新 market=%s", market)
    try:
        service = service_factory()
        exchange = ExchangeKind(market.lower())
        d1_summary = await service.sync_backfill_d1_all(exchange)
        m5_summary = await service.sync_backfill_m5_positions_candidates(exchange)
        logger.info(
            "市场K线历史更新完成 market=%s d1=%s m5=%s",
            market,
            d1_summary,
            m5_summary,
        )
    except Exception:  # noqa: BLE001
        logger.exception("市场K线历史更新失败 market=%s", market)


async def _run_market_sync(*, service_factory: Callable[[], KlineSyncService], market: str) -> None:
    logger.info("触发市场K线同步 market=%s", market)
    exchange = ExchangeKind(market.lower())
    await service_factory().sync_market(exchange)


def register_company_detail_sync_jobs(
    scheduler: AsyncIOScheduler,
    *,
    service_factory: Callable[[], CompanyDetailSyncService],
    settings: Settings | None = None,
) -> None:
    current_settings = settings or get_settings()
    # 假设共用 kline_sync.enabled_markets
    markets = current_settings.kline_sync.enabled_markets

    for market in markets:
        scheduler.add_job(
            _run_company_detail_sync,
            "cron",
            hour=22,  # 晚上 22 点进行每日详细信息同步
            minute=0,
            kwargs={"service_factory": service_factory, "market": market},
            id=f"company_detail_sync_daily_{market}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

async def _run_company_detail_sync(
    *, service_factory: Callable[[], CompanyDetailSyncService], market: str
) -> None:
    logger.info("触发市场股票详细信息同步 market=%s", market)
    try:
        service = service_factory()
        exchange = ExchangeKind(market.lower())
        await service.sync_market(exchange)
    except Exception:  # noqa: BLE001
        logger.exception("市场股票详细信息同步失败 market=%s", market)
