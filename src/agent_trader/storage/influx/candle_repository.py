from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import datetime
from typing import Any

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

    async def query_history(
        self,
        *,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 5000,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            self._query_history_sync,
            symbol,
            interval,
            start_time,
            end_time,
            limit,
        )

    def _query_history_sync(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        limit: int,
    ) -> list[dict[str, Any]]:
        escaped_symbol = symbol.replace("\\", "\\\\").replace('"', '\\"')
        escaped_interval = interval.replace("\\", "\\\\").replace('"', '\\"')
        flux = f'''
from(bucket: "{self._connection_manager.bucket}")
  |> range(start: time(v: "{start_time.isoformat()}"), stop: time(v: "{end_time.isoformat()}"))
  |> filter(fn: (r) => r._measurement == "{self.measurement}" and r.symbol == "{escaped_symbol}" and r.interval == "{escaped_interval}")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: false)
  |> limit(n: {max(int(limit), 1)})
'''
        query_api = self._connection_manager.query_api()
        tables = query_api.query(flux, org=self._connection_manager.org)
        rows: list[dict[str, Any]] = []
        for table in tables:
            for record in table.records:
                values = record.values
                bar_time = record.get_time()
                if bar_time is None:
                    continue
                rows.append(
                    {
                        "symbol": str(values.get("symbol", symbol)),
                        "interval": str(values.get("interval", interval)),
                        "bar_time": bar_time,
                        "open": float(values.get("open", 0.0)),
                        "high": float(values.get("high", 0.0)),
                        "low": float(values.get("low", 0.0)),
                        "close": float(values.get("close", 0.0)),
                        "volume": float(values.get("volume", 0.0)),
                    }
                )
        rows.sort(key=lambda item: item["bar_time"])
        return rows

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