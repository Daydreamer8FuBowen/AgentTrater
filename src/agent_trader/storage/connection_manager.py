from __future__ import annotations

import logging

from agent_trader.core.config import Settings
from agent_trader.storage.influx.client import InfluxConnectionManager
from agent_trader.storage.mongo.client import MongoConnectionManager

logger = logging.getLogger(__name__)


class AppConnectionManager:
    """统一管理 MongoDB 与 InfluxDB 的连接生命周期。"""

    def __init__(
        self,
        *,
        mongo_manager: MongoConnectionManager,
        influx_manager: InfluxConnectionManager,
    ) -> None:
        self._mongo_manager = mongo_manager
        self._influx_manager = influx_manager

    @classmethod
    def from_settings(cls, settings: Settings) -> AppConnectionManager:
        return cls(
            mongo_manager=MongoConnectionManager(settings.mongo),
            influx_manager=InfluxConnectionManager(settings.influx),
        )

    @property
    def mongo_manager(self) -> MongoConnectionManager:
        return self._mongo_manager

    @property
    def influx_manager(self) -> InfluxConnectionManager:
        return self._influx_manager

    async def start(self) -> None:
        try:
            await self._mongo_manager.ping()
            await self._mongo_manager.ensure_indexes()
            logger.info("MongoDB 连接与索引检查通过")
        except Exception as exc:  # noqa: BLE001
            logger.error("MongoDB 启动检查失败：%s", exc)
            raise

        try:
            self._influx_manager.ping()
            logger.info("InfluxDB 连接检查通过")
        except Exception as exc:  # noqa: BLE001
            logger.error("InfluxDB 启动检查失败：%s", exc)
            raise

    async def close(self) -> None:
        try:
            self._influx_manager.close()
        finally:
            await self._mongo_manager.close()
