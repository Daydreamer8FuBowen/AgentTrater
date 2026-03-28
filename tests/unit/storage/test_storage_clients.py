from unittest.mock import MagicMock

from motor.motor_asyncio import AsyncIOMotorClient

from agent_trader.core.config import InfluxConfig, MongoConfig
from agent_trader.storage.influx.client import InfluxConnectionManager
from agent_trader.storage.mongo.client import MongoConnectionManager


def test_mongo_connection_manager_lazily_creates_client_and_database() -> None:
    config = MongoConfig(
        dsn="mongodb://localhost:27017",
        database="agent_trader",
        app_name="agent-trader-tests",
    )

    manager = MongoConnectionManager(config)

    client = manager.client
    database = manager.database

    assert isinstance(client, AsyncIOMotorClient)
    assert database.name == "agent_trader"


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
