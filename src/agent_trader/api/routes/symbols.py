from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from agent_trader.api.dependencies import get_symbol_query_service
from agent_trader.api.time_serialization import serialize_temporal_payload
from agent_trader.application.services.symbol_query_service import SymbolQueryService

router = APIRouter(prefix="/symbols", tags=["symbols"])


class SymbolItemResponse(BaseModel):
    symbol: str
    name: str | None = None
    market: str | None = None
    status: str | None = None
    security_type: str | None = None
    industry: str | None = None
    area: str | None = None
    updated_at: datetime | None = None


class SymbolMonitorItemResponse(SymbolItemResponse):
    d1_completion_ratio: float = 0.0
    d1_progress_status: str = "unknown"
    latest_bar_time: datetime | None = None
    sync_status: str = "unknown"
    latest_interval: str | None = None
    lag_seconds: float = 0.0


class SymbolListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SymbolItemResponse]


class SymbolMonitorListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SymbolMonitorItemResponse]


class SymbolDetailResponse(BaseModel):
    symbol: str
    basic_info: dict[str, Any]
    sync_market: str | None = None
    sync_states: list[dict[str, Any]] = Field(default_factory=list)
    d1_progress: dict[str, Any] | None = None


@router.get("", response_model=SymbolListResponse)
async def list_symbols(
    keyword: str | None = None,
    market: str | None = None,
    status: str | None = None,
    security_type: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=200),
    service: SymbolQueryService = Depends(get_symbol_query_service),
) -> SymbolListResponse:
    payload = await service.list_symbols(
        keyword=keyword,
        market=market,
        status=status,
        security_type=security_type,
        page=page,
        page_size=page_size,
    )
    return SymbolListResponse.model_validate(serialize_temporal_payload(payload))


@router.get("/monitor", response_model=SymbolMonitorListResponse)
async def list_symbols_monitor(
    keyword: str | None = None,
    market: str | None = None,
    status: str | None = None,
    security_type: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=200),
    service: SymbolQueryService = Depends(get_symbol_query_service),
) -> SymbolMonitorListResponse:
    payload = await service.list_symbols_with_monitor(
        keyword=keyword,
        market=market,
        status=status,
        security_type=security_type,
        page=page,
        page_size=page_size,
    )
    return SymbolMonitorListResponse.model_validate(serialize_temporal_payload(payload))


@router.get("/{symbol}", response_model=SymbolDetailResponse)
async def get_symbol_detail(
    symbol: str,
    service: SymbolQueryService = Depends(get_symbol_query_service),
) -> SymbolDetailResponse:
    payload = await service.get_symbol_detail(symbol)
    if payload is None:
        raise HTTPException(status_code=404, detail="symbol not found")
    return SymbolDetailResponse.model_validate(serialize_temporal_payload(payload))
