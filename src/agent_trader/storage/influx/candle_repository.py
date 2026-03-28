from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from agent_trader.core.time import ensure_utc
from agent_trader.domain.models import Candle
from agent_trader.storage.influx.client import InfluxConnectionManager


class InfluxCandleRepository:
    """基于 InfluxDB 的 K 线写入仓储。

    写入策略：
    - 采用覆盖更新机制（自动覆盖）：相同的 timestamp + tags 会自动覆盖字段值，无需先删除。
    - timestamp 由 open_time 作为唯一时间索引，精度为秒级。
    - tags 包括：symbol, interval, asset_class, exchange, adjusted, source（6维度）。
    - 实时数据更新时，每次都获取当日全部 K 线数据（09:30-当前最近 5m 边界），通过覆盖写入来同步最新状态。
    """

    measurement = "candles"

    def __init__(self, connection_manager: InfluxConnectionManager) -> None:
        self._connection_manager = connection_manager

    async def write(self, candle: Candle) -> None:
        """写入单条 K 线数据。使用自动覆盖机制（相同 timestamp + tags 的旧数据会被覆盖）。"""
        self._write_points([self._to_point(candle)])

    async def write_batch(self, candles: Sequence[Candle]) -> None:
        """批量写入 K 线数据。使用自动覆盖机制，无需先删除历史数据。

        覆盖机制说明：
        - InfluxDB 会根据 (timestamp, tags) 对数据进行覆盖。
        - 当新写入的数据与已存在的数据有相同的 timestamp 和 tags，字段值会被覆盖。
        - 这种设计应用于实时数据更新场景，避免频繁的删除操作。
        """
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
    |> range(start: time(v: "{ensure_utc(start_time).isoformat()}"), stop: time(v: "{ensure_utc(end_time).isoformat()}"))
  |> filter(fn: (r) => r._measurement == "{self.measurement}" and r.symbol == "{escaped_symbol}" and r.interval == "{escaped_interval}")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: false)
  |> limit(n: {max(int(limit), 1)})
'''
        query_api = self._connection_manager.query_api()
        tables = query_api.query(flux, org=self._connection_manager.org)
        # 同一个 bar_time 可能来自多个 series（不同 exchange/source tag），
        # pivot 后每个 series 都产生一行，用 dict 按 bar_time 去重，
        # 优先保留 close > 0 的行（真实数据优先于零填充）。
        seen: dict[Any, dict[str, Any]] = {}
        for table in tables:
            for record in table.records:
                values = record.values
                bar_time = record.get_time()
                if bar_time is None:
                    continue
                row = {
                    "symbol": str(values.get("symbol", symbol)),
                    "interval": str(values.get("interval", interval)),
                    "bar_time": bar_time,
                    "open": float(values.get("open", 0.0)),
                    "high": float(values.get("high", 0.0)),
                    "low": float(values.get("low", 0.0)),
                    "close": float(values.get("close", 0.0)),
                    "volume": float(values.get("volume", 0.0)),
                }
                existing = seen.get(bar_time)
                if existing is None or (row["close"] > 0 and existing["close"] == 0):
                    seen[bar_time] = row
        rows = sorted(seen.values(), key=lambda item: item["bar_time"])
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
            .time(ensure_utc(candle.open_time), WritePrecision.S)
        )

        if candle.turnover is not None:
            point = point.field("turnover", candle.turnover)
        if candle.trade_count is not None:
            point = point.field("trade_count", candle.trade_count)

        return point
