#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
import logging

from agent_trader.application.data_access import DataSourceRegistry
from agent_trader.core.config import Settings
from agent_trader.core.logging import configure_logging
from agent_trader.domain.models import ExchangeKind
from agent_trader.ingestion.sources import BaoStockSource, TuShareSource
from agent_trader.storage.connection_manager import AppConnectionManager
from agent_trader.worker.factory import build_company_detail_sync_service_factory

logger = logging.getLogger(__name__)


def _build_source_registry(settings: Settings) -> DataSourceRegistry:
    registry = DataSourceRegistry()
    print(f"DEBUG: settings.tushare.token = {settings.tushare.token}")
    if settings.tushare.token:
        registry.register(TuShareSource.from_settings(settings))
    registry.register(BaoStockSource.from_settings(settings))
    print(f"DEBUG: registry.names() = {registry.names()}")
    return registry


async def _run_once(*, env_file: str, market: list[str] | None) -> None:
    settings = Settings(_env_file=env_file)
    configure_logging(settings.log_level)

    connections = AppConnectionManager.from_settings(settings)
    await connections.start()
    try:
        source_registry = _build_source_registry(settings)
        service_factory = build_company_detail_sync_service_factory(
            database=connections.mongo_manager.database,
            source_registry=source_registry,
        )
        service = service_factory()

        markets = market if market else settings.kline_sync.enabled_markets
        for current_market in markets:
            exchange = ExchangeKind(current_market.lower())
            logger.info("开始执行一次 CompanyDetailSyncService，同步市场=%s", exchange)
            await service.sync_market(exchange)
            logger.info("CompanyDetailSyncService 执行完成，市场=%s", exchange)
    finally:
        await connections.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=".env.local")
    parser.add_argument("--market", nargs="*", default=["sse", "szse"])
    args = parser.parse_args()
    asyncio.run(_run_once(env_file=args.env_file, market=args.market))


if __name__ == "__main__":
    main()
