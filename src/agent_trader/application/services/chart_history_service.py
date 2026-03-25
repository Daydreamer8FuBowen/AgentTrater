from __future__ import annotations

from datetime import datetime
from typing import Any

from agent_trader.storage.base import CandleRepository


_RESOLUTION_TO_INTERVAL = {
    "1": "1m",
    "3": "3m",
    "5": "5m",
    "15": "15m",
    "30": "30m",
    "60": "1h",
    "240": "4h",
    "D": "1d",
    "W": "1w",
    "M": "1mo",
}


class ChartHistoryService:
    def __init__(self, candle_repository: CandleRepository) -> None:
        self._candle_repository = candle_repository

    async def get_tv_history(
        self,
        *,
        symbol: str,
        resolution: str,
        from_ts: int,
        to_ts: int,
        countback: int | None = None,
    ) -> dict[str, Any]:
        interval = self._to_interval(resolution)
        start_time = datetime.utcfromtimestamp(from_ts)
        end_time = datetime.utcfromtimestamp(to_ts)
        if end_time < start_time:
            raise ValueError("invalid time range")

        rows = await self._candle_repository.query_history(
            symbol=symbol.strip().upper(),
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            limit=max(countback or 5000, 1),
        )
        if not rows:
            return {"s": "no_data"}

        ordered_rows = sorted(rows, key=lambda item: item["bar_time"])
        if countback is not None and countback > 0 and len(ordered_rows) > countback:
            ordered_rows = ordered_rows[-countback:]

        return {
            "s": "ok",
            "t": [int(item["bar_time"].timestamp()) for item in ordered_rows],
            "o": [float(item.get("open", 0.0) or 0.0) for item in ordered_rows],
            "h": [float(item.get("high", 0.0) or 0.0) for item in ordered_rows],
            "l": [float(item.get("low", 0.0) or 0.0) for item in ordered_rows],
            "c": [float(item.get("close", 0.0) or 0.0) for item in ordered_rows],
            "v": [float(item.get("volume", 0.0) or 0.0) for item in ordered_rows],
        }

    def _to_interval(self, resolution: str) -> str:
        value = resolution.strip().upper()
        if value not in _RESOLUTION_TO_INTERVAL:
            raise ValueError(f"unsupported resolution: {resolution}")
        return _RESOLUTION_TO_INTERVAL[value]
