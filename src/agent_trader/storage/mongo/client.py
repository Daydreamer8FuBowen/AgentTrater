"""Mongo 连接与索引管理。

本模块提供创建 Motor 异步客户端、获取数据库句柄以及一个连接管理器 `MongoConnectionManager`。

建议在应用启动阶段使用 `MongoConnectionManager` 的 `ensure_indexes()` 方法根据
`schema.DOCUMENT_REGISTRY` 创建所需索引，启动完成后在关闭钩子中调用 `close()`。
"""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from agent_trader.core.config import MongoConfig
from agent_trader.storage.mongo.schema import DOCUMENT_REGISTRY


def create_mongo_client(config: MongoConfig) -> AsyncIOMotorClient:
    """创建并返回一个 Motor 异步 Mongo 客户端。

    参数:
      - config: 包含 `dsn` 与 `app_name` 的 `MongoConfig`。

    返回值:
      - `AsyncIOMotorClient` 实例（lazy 创建交由调用方管理）。
    """
    return AsyncIOMotorClient(config.dsn, appname=config.app_name, uuidRepresentation="standard")


def create_mongo_database(client: AsyncIOMotorClient, database_name: str) -> AsyncIOMotorDatabase:
    """从客户端获取指定名称的数据库对象。"""
    return client[database_name]


class MongoConnectionManager:
    """MongoDB 连接管理器。

    用法示例:

    ```py
    mgr = MongoConnectionManager(settings.mongo)
    await mgr.ping()
    await mgr.ensure_indexes()
    db = mgr.database
    # 使用 db 执行数据操作
    await mgr.close()
    ```
    """

    def __init__(self, config: MongoConfig) -> None:
        self._config = config
        self._client: AsyncIOMotorClient | None = None
        self._database: AsyncIOMotorDatabase | None = None

    @property
    def client(self) -> AsyncIOMotorClient:
        """惰性创建并返回 `AsyncIOMotorClient`。"""
        if self._client is None:
            self._client = create_mongo_client(self._config)
        return self._client

    @property
    def database(self) -> AsyncIOMotorDatabase:
        """惰性获取并返回配置的数据库句柄。"""
        if self._database is None:
            self._database = create_mongo_database(self.client, self._config.database)
        return self._database

    async def ping(self) -> bool:
        """简单的 ping 检查，确认与 Mongo 的连通性。"""
        await self.database.command("ping")
        return True

    async def ensure_indexes(self) -> None:
        """根据 `schema.DOCUMENT_REGISTRY` 为每个集合创建声明的索引。

        该方法适合在应用启动时运行一次，确保索引可用。
        """
        for config in DOCUMENT_REGISTRY.values():
            if not config.indexes:
                continue
            await self.database[config.name].create_indexes(list(config.indexes))

    async def close(self) -> None:
        """关闭底层 Motor 客户端连接。"""
        if self._client is not None:
            self._client.close()


def create_mongo_connection_manager(config: MongoConfig) -> MongoConnectionManager:
    """工厂函数：使用 `MongoConfig` 创建 `MongoConnectionManager` 实例。"""
    return MongoConnectionManager(config)
