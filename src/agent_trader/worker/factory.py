from __future__ import annotations

from collections.abc import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from motor.motor_asyncio import AsyncIOMotorDatabase

from agent_trader.application.data_access import DataAccessGateway, DataSourceRegistry, SourceSelectionAdapter
from agent_trader.application.services.kline_sync_service import KlineSyncService, TierCollectionService
from agent_trader.core.config import Settings, get_settings
from agent_trader.storage.influx import InfluxCandleRepository, InfluxConnectionManager
from agent_trader.storage.mongo import MongoUnitOfWork
from agent_trader.storage.mongo.repository import MongoSourcePriorityRepository


def create_scheduler(settings: Settings | None = None) -> AsyncIOScheduler:
    current_settings = settings or get_settings()
    return AsyncIOScheduler(timezone=current_settings.worker.timezone)


def build_kline_sync_service_factory(
    *,
    database: AsyncIOMotorDatabase,
    influx_manager: InfluxConnectionManager,
    source_registry: DataSourceRegistry,
    settings: Settings | None = None,
) -> Callable[[], KlineSyncService]:
    current_settings = settings or get_settings()

    def _factory() -> KlineSyncService:
        selector = SourceSelectionAdapter(
            registry=source_registry,
            priority_repository=MongoSourcePriorityRepository(database),
        )
        gateway = DataAccessGateway(selector)
        uow_factory = lambda: MongoUnitOfWork(database)
        tier_collection_service = TierCollectionService(uow_factory)
        candle_repository = InfluxCandleRepository(influx_manager)
        return KlineSyncService(
            gateway=gateway,
            candle_repository=candle_repository,
            uow_factory=uow_factory,
            tier_collection_service=tier_collection_service,
            config=current_settings.kline_sync,
        )

    return _factory
