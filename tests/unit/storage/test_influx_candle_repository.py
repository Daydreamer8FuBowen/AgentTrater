from datetime import datetime, timezone
from unittest.mock import MagicMock

from agent_trader.core.config import InfluxConfig
from agent_trader.domain.models import AssetClass, BarInterval, Candle, ExchangeKind
from agent_trader.storage.influx.candle_repository import InfluxCandleRepository
from agent_trader.storage.influx.client import InfluxConnectionManager


def build_candle() -> Candle:
    return Candle(
        symbol="AAPL",
        interval=BarInterval.M1,
        open_time=datetime(2026, 3, 19, 9, 30, tzinfo=timezone.utc),
        close_time=datetime(2026, 3, 19, 9, 31, tzinfo=timezone.utc),
        open_price=100.0,
        high_price=101.5,
        low_price=99.8,
        close_price=101.0,
        volume=12345.0,
        turnover=1_200_000.0,
        trade_count=456,
        asset_class=AssetClass.STOCK,
        exchange=ExchangeKind.NASDAQ,
        adjusted=True,
        source="polygon",
    )


def build_manager() -> InfluxConnectionManager:
    return InfluxConnectionManager(
        InfluxConfig(
            url="http://localhost:8086",
            token="token",
            org="org",
            bucket="finance",
            timeout_ms=10_000,
        )
    )


def test_candle_to_ohlcv() -> None:
    candle = build_candle()

    assert candle.to_ohlcv() == {
        "open": 100.0,
        "high": 101.5,
        "low": 99.8,
        "close": 101.0,
        "volume": 12345.0,
    }


def test_influx_candle_repository_writes_point() -> None:
    manager = build_manager()
    mock_write_api = MagicMock()
    mock_client = MagicMock()
    mock_client.write_api.return_value = mock_write_api
    manager._client = mock_client
    repository = InfluxCandleRepository(manager)

    point = repository._to_point(build_candle())
    line = point.to_line_protocol()

    assert "candles" in line
    assert "symbol=AAPL" in line
    assert "interval=1m" in line
    assert "exchange=nasdaq" in line
    assert "open=100" in line
    assert "close=101" in line


async def test_influx_candle_repository_write_batch_uses_bucket_and_org() -> None:
    manager = build_manager()
    mock_write_api = MagicMock()
    mock_client = MagicMock()
    mock_client.write_api.return_value = mock_write_api
    manager._client = mock_client
    repository = InfluxCandleRepository(manager)

    await repository.write_batch([build_candle()])

    mock_write_api.write.assert_called_once()
    call_kwargs = mock_write_api.write.call_args.kwargs
    assert call_kwargs["bucket"] == "finance"
    assert call_kwargs["org"] == "org"
    assert len(call_kwargs["record"]) == 1
