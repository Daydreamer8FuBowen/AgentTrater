from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from agent_trader.api.dependencies import get_table_admin_service
from agent_trader.application.services.table_admin_service import TableAdminService

router = APIRouter(prefix="/admin/tables", tags=["admin-tables"])


class TableMetadata(BaseModel):
    name: str
    primary_key: str
    columns: list[str]
    searchable_columns: list[str]
    json_columns: list[str]


class TableRowsResponse(BaseModel):
    table: str
    page: int
    page_size: int
    total: int
    items: list[dict[str, Any]]


class RowUpdateRequest(BaseModel):
    updates: dict[str, Any] = Field(default_factory=dict)


@router.get("", response_model=list[TableMetadata])
async def list_manageable_tables(
    service: TableAdminService = Depends(get_table_admin_service),
) -> list[dict[str, Any]]:
    return service.list_tables()


@router.get("/{table_name}/rows", response_model=TableRowsResponse)
async def query_table_rows(
    table_name: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = Query(default=None, max_length=200),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="desc", pattern="^(asc|desc|ASC|DESC)$"),
    filters: str | None = Query(default=None),
    service: TableAdminService = Depends(get_table_admin_service),
) -> dict[str, Any]:
    parsed_filters: dict[str, Any] = {}
    if filters:
        try:
            candidate = json.loads(filters)
            if isinstance(candidate, dict):
                parsed_filters = candidate
            else:
                raise ValueError("filters must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    try:
        return await service.query_rows(
            table_name,
            page=page,
            page_size=page_size,
            keyword=keyword,
            filters=parsed_filters,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{table_name}/rows/{row_id}")
async def get_table_row(
    table_name: str,
    row_id: str,
    service: TableAdminService = Depends(get_table_admin_service),
) -> dict[str, Any]:
    try:
        row = await service.get_row(table_name, row_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Row not found")
    return row


@router.patch("/{table_name}/rows/{row_id}")
async def update_table_row(
    table_name: str,
    row_id: str,
    payload: RowUpdateRequest,
    service: TableAdminService = Depends(get_table_admin_service),
) -> dict[str, Any]:
    if not payload.updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="updates payload is required",
        )

    try:
        row = await service.update_row(table_name, row_id, payload.updates)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Row not found")
    return row