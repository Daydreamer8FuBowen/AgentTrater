from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from agent_trader.api.dependencies import get_chart_history_service
from agent_trader.application.services.chart_history_service import ChartHistoryService

router = APIRouter(prefix="/charts", tags=["charts"])


@router.get("/history")
async def get_history(
    symbol: str,
    resolution: str,
    from_ts: int = Query(alias="from"),
    to_ts: int = Query(alias="to"),
    countback: int | None = Query(default=None, ge=1),
    service: ChartHistoryService = Depends(get_chart_history_service),
) -> dict[str, Any]:
    try:
        return await service.get_tv_history(
            symbol=symbol,
            resolution=resolution,
            from_ts=from_ts,
            to_ts=to_ts,
            countback=countback,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
