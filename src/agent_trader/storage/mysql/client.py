from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from agent_trader.core.config import MySQLConfig


def create_mysql_engine(config: MySQLConfig) -> AsyncEngine:
    """根据统一配置创建 MySQL 异步引擎。"""

    return create_async_engine(
        config.dsn,
        echo=config.echo,
        pool_pre_ping=True,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
    )


def create_mysql_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """为业务层提供可复用的 AsyncSession 工厂。"""

    return async_sessionmaker(engine, expire_on_commit=False)


class MySQLConnectionManager:
    """MySQL 连接管理器。

    负责统一管理 engine、session factory、健康检查和连接释放，
    后续 repository / unit of work 直接依赖它即可。
    """

    def __init__(self, config: MySQLConfig) -> None:
        self._config = config
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            self._engine = create_mysql_engine(self._config)
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            self._session_factory = create_mysql_session_factory(self.engine)
        return self._session_factory

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """以统一方式为调用方提供数据库会话。"""

        async with self.session_factory() as session:
            yield session

    async def ping(self) -> bool:
        """执行最小查询，验证数据库连通性。"""

        async with self.session() as session:
            await session.execute(text("SELECT 1"))
        return True

    async def close(self) -> None:
        """释放 engine 持有的连接池资源。"""

        if self._engine is not None:
            await self._engine.dispose()


def create_mysql_connection_manager(config: MySQLConfig) -> MySQLConnectionManager:
    """创建 MySQL 连接管理器的统一工厂方法。"""

    return MySQLConnectionManager(config)