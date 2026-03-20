from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from agent_trader.storage.mongo.schema import DOCUMENT_REGISTRY, DocumentConfig


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


class TableAdminService:
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._database = database

    def list_tables(self) -> list[dict[str, Any]]:
        return [
            {
                "name": cfg.name,
                "primary_key": cfg.primary_key,
                "columns": list(cfg.columns),
                "searchable_columns": list(cfg.searchable_columns),
                "json_columns": list(cfg.json_columns),
            }
            for cfg in DOCUMENT_REGISTRY.values()
        ]

    def _get_table(self, table_name: str) -> DocumentConfig:
        cfg = DOCUMENT_REGISTRY.get(table_name)
        if cfg is None:
            raise ValueError(f"Unsupported table: {table_name}")
        return cfg

    def _build_query(self, cfg: DocumentConfig, keyword: str | None, filters: dict[str, Any]) -> dict[str, Any]:
        query: dict[str, Any] = {}

        if keyword:
            query["$or"] = [
                {column: {"$regex": keyword.strip(), "$options": "i"}}
                for column in cfg.searchable_columns
            ]

        for column, value in filters.items():
            if column not in cfg.columns:
                continue
            if value is None or value == "":
                continue
            query[column] = value

        return query

    async def query_rows(
        self,
        table_name: str,
        *,
        page: int,
        page_size: int,
        keyword: str | None = None,
        filters: dict[str, Any] | None = None,
        sort_by: str | None = None,
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        cfg = self._get_table(table_name)
        collection = self._database[cfg.name]
        query = self._build_query(cfg, keyword, filters or {})

        sort_field = sort_by if sort_by in cfg.columns else cfg.primary_key
        sort_direction = -1 if sort_order.lower() == "desc" else 1
        total = await collection.count_documents(query)
        cursor = collection.find(query, {"_id": 0}).sort(sort_field, sort_direction).skip((page - 1) * page_size).limit(page_size)
        items = [_to_jsonable(row) async for row in cursor]

        return {
            "table": cfg.name,
            "page": page,
            "page_size": page_size,
            "total": total,
            "items": items,
        }

    async def get_row(self, table_name: str, row_id: str) -> dict[str, Any] | None:
        cfg = self._get_table(table_name)
        collection = self._database[cfg.name]
        row = await collection.find_one({cfg.primary_key: row_id}, {"_id": 0})
        if row is None:
            return None
        return _to_jsonable(row)

    async def update_row(self, table_name: str, row_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        cfg = self._get_table(table_name)
        collection = self._database[cfg.name]
        valid_updates = {
            key: value
            for key, value in updates.items()
            if key in cfg.editable_columns and key != cfg.primary_key
        }
        if not valid_updates:
            raise ValueError("No editable columns in update payload")

        normalized_updates: dict[str, Any] = {}
        for column, value in valid_updates.items():
            if column in cfg.json_columns and isinstance(value, str):
                normalized_updates[column] = json.loads(value)
                continue
            normalized_updates[column] = value

        if "updated_at" in cfg.columns and "updated_at" not in normalized_updates:
            normalized_updates["updated_at"] = datetime.utcnow()

        result = await collection.update_one(
            {cfg.primary_key: row_id},
            {"$set": normalized_updates},
        )
        if result.matched_count == 0:
            return None

        return await self.get_row(cfg.name, row_id)