from __future__ import annotations

from collections.abc import Sequence

from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from agent_trader.domain.models import Candle
from agent_trader.storage.influx.client import InfluxConnectionManager


class InfluxCandleRepository:
    """基于 InfluxDB 的 K 线写入仓储。"""

    measurement = "candles"

    def __init__(self, connection_manager: InfluxConnectionManager) -> None:
        self._connection_manager = connection_manager

    async def write(self, candle: Candle) -> None:
        self._write_points([self._to_point(candle)])

    async def write_batch(self, candles: Sequence[Candle]) -> None:
        points = [self._to_point(candle) for candle in candles]
        if not points:
            return
        self._write_points(points)

    def _write_points(self, points: list[Point]) -> None:
        write_api = self._connection_manager.client.write_api(write_options=SYNCHRONOUS)
        write_api.write(
            bucket=self._connection_manager.bucket,
            org=self._connection_manager.org,
            record=points,
            write_precision=WritePrecision.S,
        )

    def _to_point(self, candle: Candle) -> Point:
        point = (
            Point(self.measurement)
            .tag("symbol", candle.symbol)
            .tag("interval", candle.interval.value)
            .tag("asset_class", candle.asset_class.value)
            .tag("exchange", candle.exchange.value)
            .tag("adjusted", str(candle.adjusted).lower())
            .tag("source", candle.source)
            .field("open", candle.open_price)
            .field("high", candle.high_price)
            .field("low", candle.low_price)
            .field("close", candle.close_price)
            .field("volume", candle.volume)
            .time(candle.open_time, WritePrecision.S)
        )

        if candle.turnover is not None:
            point = point.field("turnover", candle.turnover)
        if candle.trade_count is not None:
            point = point.field("trade_count", candle.trade_count)

        point = point.field("close_ts", int(candle.close_time.timestamp()))

        return point