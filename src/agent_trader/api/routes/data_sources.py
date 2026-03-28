from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from agent_trader.api.dependencies import (
    get_mongo_database,
    get_source_priority_repository,
    get_source_registry,
)
from agent_trader.application.data_access.gateway import DataSourceRegistry
from agent_trader.domain.models import BarInterval, ExchangeKind
from agent_trader.ingestion.models import DataCapability, DataRouteKey
from agent_trader.storage.base import SourcePriorityRepository
from agent_trader.storage.mongo.documents import SourcePriorityRouteDocument

router = APIRouter(prefix="/data-sources", tags=["data_sources"])


class SourceCapabilityResponse(BaseModel):
    capability: str
    markets: list[str] = Field(default_factory=list)
    intervals: list[str] = Field(default_factory=list)


class DataSourceResponse(BaseModel):
    name: str
    capabilities: list[SourceCapabilityResponse] = Field(default_factory=list)


class RoutePriorityResponse(BaseModel):
    route_id: str
    capability: str
    market: str | None = None
    interval: str | None = None
    supported_sources: list[str] = Field(default_factory=list)
    priorities: list[str] = Field(default_factory=list)
    enabled: bool = True


class DataSourceRoutesOverviewResponse(BaseModel):
    sources: list[DataSourceResponse]
    routes: list[RoutePriorityResponse]


class UpdateRoutePriorityRequest(BaseModel):
    priorities: list[str] = Field(min_length=1)
    enabled: bool | None = None


def _build_supported_routes(registry: DataSourceRegistry) -> dict[str, RoutePriorityResponse]:
    routes: dict[str, RoutePriorityResponse] = {}
    for source_name in registry.names():
        provider = registry.get(source_name)
        if provider is None:
            continue
        capabilities = getattr(provider, "capabilities", None)
        if not callable(capabilities):
            continue
        for spec in capabilities():
            markets = spec.markets or (None,)
            intervals = spec.intervals or (None,)
            for market in markets:
                for interval in intervals:
                    route_key = DataRouteKey(
                        capability=spec.capability,
                        market=market,
                        interval=interval,
                    )
                    route_id = route_key.as_storage_key()
                    route = routes.get(route_id)
                    if route is None:
                        route = RoutePriorityResponse(
                            route_id=route_id,
                            capability=route_key.capability.value,
                            market=route_key.market.value if route_key.market else None,
                            interval=route_key.interval.value if route_key.interval else None,
                            supported_sources=[],
                            priorities=[],
                            enabled=True,
                        )
                        routes[route_id] = route
                    if source_name not in route.supported_sources:
                        route.supported_sources.append(source_name)
    for route in routes.values():
        route.priorities = list(route.supported_sources)
    return routes


def _parse_route_id(route_id: str) -> DataRouteKey:
    parts = route_id.split(":")
    if len(parts) != 3:
        raise ValueError("route_id format must be capability:market:interval")
    capability_raw, market_raw, interval_raw = parts
    capability = DataCapability(capability_raw)
    market = None if market_raw == "*" else ExchangeKind(market_raw)
    interval = None if interval_raw == "*" else BarInterval(interval_raw)
    return DataRouteKey(capability=capability, market=market, interval=interval)


def _serialize_source(source_name: str, provider: object) -> DataSourceResponse:
    capabilities_method = getattr(provider, "capabilities", None)
    if not callable(capabilities_method):
        return DataSourceResponse(name=source_name, capabilities=[])
    items = []
    for spec in capabilities_method():
        items.append(
            SourceCapabilityResponse(
                capability=spec.capability.value,
                markets=[item.value for item in spec.markets],
                intervals=[item.value for item in spec.intervals],
            )
        )
    return DataSourceResponse(name=source_name, capabilities=items)


@router.get("/routes", response_model=DataSourceRoutesOverviewResponse)
async def list_data_source_routes(
    registry: Annotated[DataSourceRegistry, Depends(get_source_registry)],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_mongo_database)],
) -> DataSourceRoutesOverviewResponse:
    route_map = _build_supported_routes(registry)
    collection = database[SourcePriorityRouteDocument.collection_name]
    records = await collection.find({}, {"_id": 0}).to_list(length=5000)
    for record in records:
        route_id = str(record.get("route_id", ""))
        if not route_id:
            continue
        route = route_map.get(route_id)
        priorities = [str(item) for item in record.get("priorities", [])]
        enabled = bool(record.get("enabled", True))
        if route is None:
            route = RoutePriorityResponse(
                route_id=route_id,
                capability=str(record.get("capability", "")),
                market=record.get("market"),
                interval=record.get("interval"),
                supported_sources=list(priorities),
                priorities=list(priorities),
                enabled=enabled,
            )
            route_map[route_id] = route
            continue
        route.priorities = priorities
        route.enabled = enabled
    sources: list[DataSourceResponse] = []
    for source_name in registry.names():
        provider = registry.get(source_name)
        if provider is None:
            continue
        sources.append(_serialize_source(source_name, provider))
    routes = sorted(
        route_map.values(),
        key=lambda item: (
            item.capability,
            item.market or "*",
            item.interval or "*",
            item.route_id,
        ),
    )
    return DataSourceRoutesOverviewResponse(sources=sources, routes=routes)


@router.patch("/routes/{route_id}", response_model=RoutePriorityResponse)
async def update_data_source_route_priority(
    route_id: str,
    payload: UpdateRoutePriorityRequest,
    registry: Annotated[DataSourceRegistry, Depends(get_source_registry)],
    repository: Annotated[SourcePriorityRepository, Depends(get_source_priority_repository)],
) -> RoutePriorityResponse:
    try:
        route_key = _parse_route_id(route_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    route_map = _build_supported_routes(registry)
    supported_route = route_map.get(route_id)
    if supported_route is None:
        raise HTTPException(status_code=404, detail="route not found")

    priorities = list(payload.priorities)
    if len(priorities) != len(set(priorities)):
        raise HTTPException(status_code=400, detail="priorities contains duplicate source")
    supported_set = set(supported_route.supported_sources)
    provided_set = set(priorities)
    if provided_set != supported_set:
        raise HTTPException(
            status_code=400,
            detail="priorities must contain all supported sources exactly once",
        )

    existing = await repository.get(route_key)
    metadata: dict[str, Any] = {}
    enabled = True
    if existing is not None:
        metadata = dict(getattr(existing, "metadata", {}))
        enabled = bool(getattr(existing, "enabled", True))
    if payload.enabled is not None:
        enabled = payload.enabled

    await repository.upsert(
        route_key,
        priorities=priorities,
        enabled=enabled,
        metadata=metadata,
    )
    return RoutePriorityResponse(
        route_id=route_key.as_storage_key(),
        capability=route_key.capability.value,
        market=route_key.market.value if route_key.market else None,
        interval=route_key.interval.value if route_key.interval else None,
        supported_sources=list(supported_route.supported_sources),
        priorities=priorities,
        enabled=enabled,
    )
