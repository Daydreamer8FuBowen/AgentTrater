from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from agent_trader.core.config import MongoConfig
from agent_trader.storage.mongo.schema import DOCUMENT_REGISTRY


def create_mongo_client(config: MongoConfig) -> AsyncIOMotorClient:
    return AsyncIOMotorClient(config.dsn, appname=config.app_name, uuidRepresentation="standard")


def create_mongo_database(client: AsyncIOMotorClient, database_name: str) -> AsyncIOMotorDatabase:
    return client[database_name]


class MongoConnectionManager:
    """MongoDB 连接管理器。"""

    def __init__(self, config: MongoConfig) -> None:
        self._config = config
        self._client: AsyncIOMotorClient | None = None
        self._database: AsyncIOMotorDatabase | None = None

    @property
    def client(self) -> AsyncIOMotorClient:
        if self._client is None:
            self._client = create_mongo_client(self._config)
        return self._client

    @property
    def database(self) -> AsyncIOMotorDatabase:
        if self._database is None:
            self._database = create_mongo_database(self.client, self._config.database)
        return self._database

    async def ping(self) -> bool:
        await self.database.command("ping")
        return True

    async def ensure_indexes(self) -> None:
        for config in DOCUMENT_REGISTRY.values():
            if not config.indexes:
                continue
            await self.database[config.name].create_indexes(list(config.indexes))

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()


def create_mongo_connection_manager(config: MongoConfig) -> MongoConnectionManager:
    return MongoConnectionManager(config)