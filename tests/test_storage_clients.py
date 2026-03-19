from unittest.mock import MagicMock

from sqlalchemy.ext.asyncio import AsyncEngine

from agent_trader.core.config import InfluxConfig, MySQLConfig
from agent_trader.storage.influx.client import InfluxConnectionManager
from agent_trader.storage.mysql.client import MySQLConnectionManager


def test_mysql_connection_manager_lazily_creates_engine() -> None:
    config = MySQLConfig(
        dsn="mysql+asyncmy://root:root@localhost:3306/agent_trader",
        echo=False,
        pool_size=10,
        max_overflow=20,
    )

    manager = MySQLConnectionManager(config)

    engine = manager.engine

    assert isinstance(engine, AsyncEngine)
    assert manager.session_factory is not None


def test_influx_connection_manager_uses_bucket_and_org() -> None:
    config = InfluxConfig(
        url="http://localhost:8086",
        token="token",
        org="org",
        bucket="finance",
        timeout_ms=10_000,
    )

    manager = InfluxConnectionManager(config)
    mock_client = MagicMock()
    manager._client = mock_client

    assert manager.org == "org"
    assert manager.bucket == "finance"
    assert manager.query_api() is mock_client.query_api.return_value
    assert manager.write_api() is mock_client.write_api.return_value