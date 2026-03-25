"""Mongo 仓库实现（任务相关的增删改查示例）。

本模块包含对 `task_runs`, `task_events`, `task_artifacts` 三个集合的简单仓库实现，
用于演示如何在应用中封装数据库操作。生产环境中可按需扩展更多查询/分页/过滤方法。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateOne

from agent_trader.ingestion.models import DataRouteKey
from agent_trader.storage.mongo.documents import (
    BackfillProgressDocument,
    BasicInfoDocument,
    CandidateDocument,
    KlineSyncStateDocument,
    NewsDocument,
    PositionDocument,
    SourcePriorityRouteDocument,
    TaskArtifactDocument,
    TaskEventDocument,
    TaskRunDocument,
)


def _task_run_update_timestamp() -> dict[str, datetime]:
    """辅助函数：返回用于更新 `updated_at` 字段的 dict。"""
    return {"updated_at": datetime.utcnow()}


class MongoTaskRunRepository:
    """针对集合 `task_runs` 的基础仓库实现。

    提供：新增（add）、按 `run_id` 获取（get）、以及更新状态的快捷方法（mark_running/mark_completed/mark_failed）。
    """

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._collection = database[TaskRunDocument.collection_name]

    async def add(self, task_run: TaskRunDocument) -> TaskRunDocument:
        """插入一个新的 TaskRun 文档并返回原对象（已序列化）。"""
        await self._collection.insert_one(task_run.model_dump())
        return task_run

    async def get(self, run_id: str) -> TaskRunDocument | None:
        """根据主键 `run_id` 查询并返回 `TaskRunDocument` 实例，若不存在返回 None。"""
        payload = await self._collection.find_one({TaskRunDocument.primary_key: run_id}, {"_id": 0})
        return None if payload is None else TaskRunDocument.model_validate(payload)

    async def mark_running(self, run_id: str) -> None:
        """将某个 run 标记为 running，并写入开始时间与更新时间。"""
        await self._collection.update_one(
            {TaskRunDocument.primary_key: run_id},
            {
                "$set": {
                    "status": "running",
                    "execution.started_at": datetime.utcnow(),
                    **_task_run_update_timestamp(),
                }
            },
        )

    async def mark_completed(self, run_id: str, *, result_summary: str | None) -> None:
        """将 run 标记为 completed，并写入结果摘要与完成时间。"""
        await self._collection.update_one(
            {TaskRunDocument.primary_key: run_id},
            {
                "$set": {
                    "status": "completed",
                    "result.summary": result_summary,
                    "execution.finished_at": datetime.utcnow(),
                    **_task_run_update_timestamp(),
                }
            },
        )

    async def mark_failed(self, run_id: str, *, error_message: str) -> None:
        """将 run 标记为 failed，并记录错误信息与完成时间。"""
        await self._collection.update_one(
            {TaskRunDocument.primary_key: run_id},
            {
                "$set": {
                    "status": "failed",
                    "error": {"message": error_message},
                    "execution.finished_at": datetime.utcnow(),
                    **_task_run_update_timestamp(),
                }
            },
        )


class MongoTaskEventRepository:
    """针对集合 `task_events` 的基础仓库实现（仅示例的新增方法）。"""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._collection = database[TaskEventDocument.collection_name]

    async def add(self, event: TaskEventDocument) -> TaskEventDocument:
        """插入事件文档。"""
        await self._collection.insert_one(event.model_dump())
        return event


class MongoTaskArtifactRepository:
    """针对集合 `task_artifacts` 的基础仓库实现（示例插入）。"""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._collection = database[TaskArtifactDocument.collection_name]

    async def add(self, artifact: TaskArtifactDocument) -> TaskArtifactDocument:
        """插入产物文档并返回原对象。"""
        payload: dict[str, Any] = artifact.model_dump()
        await self._collection.insert_one(payload)
        return artifact


class MongoNewsRepository:
    """新闻集合仓储实现。"""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._collection = database[NewsDocument.collection_name]

    async def add(self, news: NewsDocument) -> NewsDocument:
        await self._collection.insert_one(news.model_dump())
        return news

    async def add_many(self, items: list[NewsDocument]) -> list[NewsDocument]:
        if not items:
            return []
        await self._collection.insert_many([item.model_dump() for item in items], ordered=False)
        return items

    async def exists_by_dedupe_key(self, dedupe_key: str) -> bool:
        payload = await self._collection.find_one({"dedupe_key": dedupe_key}, {"_id": 0, "dedupe_key": 1})
        return payload is not None


class MongoBasicInfoRepository:
    """标的基础信息快照仓储实现。"""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._collection = database[BasicInfoDocument.collection_name]

    async def upsert_many_by_symbol(self, items: list[BasicInfoDocument]) -> dict[str, int]:
        if not items:
            return {
                "requested": 0,
                "matched": 0,
                "modified": 0,
                "upserted": 0,
            }

        operations: list[UpdateOne] = []
        for item in items:
            payload = item.model_dump()
            created_at = payload.pop("created_at", datetime.utcnow())
            operations.append(
                UpdateOne(
                    {"symbol": item.symbol},
                    {
                        "$set": payload,
                        "$setOnInsert": {"created_at": created_at},
                    },
                    upsert=True,
                )
            )

        result = await self._collection.bulk_write(operations, ordered=False)
        return {
            "requested": len(items),
            "matched": result.matched_count,
            "modified": result.modified_count,
            "upserted": result.upserted_count,
        }

    async def list_symbols_by_market(self, market: str) -> list[str]:
        """按市场查询可参与 Tier 分层的 symbol。"""
        query: dict[str, Any] = {
            "market": market,
            "status": {"$nin": ["delisted", "0", 0]},
        }
        if market in {"sh", "sz"}:
            query["security_type"] = "stock"
            query["name"] = {"$not": re.compile("ST")}

        cursor = self._collection.find(query, {"symbol": 1, "_id": 0})
        docs = await cursor.to_list(length=None)
        return [doc["symbol"] for doc in docs]


class MongoSourcePriorityRepository:
    """数据源路由优先级配置仓储。"""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._collection = database[SourcePriorityRouteDocument.collection_name]

    async def get(self, route_key: DataRouteKey) -> SourcePriorityRouteDocument | None:
        payload = await self._collection.find_one(
            {"route_id": route_key.as_storage_key()},
            {"_id": 0},
        )
        return None if payload is None else SourcePriorityRouteDocument.model_validate(payload)

    async def upsert(
        self,
        route_key: DataRouteKey,
        *,
        priorities: list[str],
        enabled: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> SourcePriorityRouteDocument:
        route = SourcePriorityRouteDocument(
            route_id=route_key.as_storage_key(),
            capability=route_key.capability.value,
            market=route_key.market.value if route_key.market else None,
            interval=route_key.interval.value if route_key.interval else None,
            priorities=priorities,
            enabled=enabled,
            metadata=metadata or {},
        )
        await self._collection.update_one(
            {"route_id": route.route_id},
            {"$set": route.model_dump()},
            upsert=True,
        )
        return route

    async def reorder(self, route_key: DataRouteKey, *, priorities: list[str]) -> None:
        await self._collection.update_one(
            {"route_id": route_key.as_storage_key()},
            {
                "$set": {
                    "priorities": priorities,
                    "updated_at": datetime.utcnow(),
                }
            },
        )


class MongoCandidateRepository:
    """候选池集合仓储实现。"""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._collection = database[CandidateDocument.collection_name]

    async def upsert(self, candidate: CandidateDocument) -> CandidateDocument:
        payload = candidate.model_dump()
        created_at = payload.pop("created_at", datetime.utcnow())
        await self._collection.update_one(
            {CandidateDocument.primary_key: candidate.candidate_id},
            {
                "$set": payload,
                "$setOnInsert": {"created_at": created_at},
            },
            upsert=True,
        )
        return candidate

    async def upsert_many(self, items: list[CandidateDocument]) -> dict[str, int]:
        if not items:
            return {
                "requested": 0,
                "matched": 0,
                "modified": 0,
                "upserted": 0,
            }

        operations: list[UpdateOne] = []
        for item in items:
            payload = item.model_dump()
            created_at = payload.pop("created_at", datetime.utcnow())
            operations.append(
                UpdateOne(
                    {CandidateDocument.primary_key: item.candidate_id},
                    {
                        "$set": payload,
                        "$setOnInsert": {"created_at": created_at},
                    },
                    upsert=True,
                )
            )

        result = await self._collection.bulk_write(operations, ordered=False)
        return {
            "requested": len(items),
            "matched": result.matched_count,
            "modified": result.modified_count,
            "upserted": result.upserted_count,
        }

    async def get_by_id(self, candidate_id: str) -> CandidateDocument | None:
        payload = await self._collection.find_one({CandidateDocument.primary_key: candidate_id}, {"_id": 0})
        return None if payload is None else CandidateDocument.model_validate(payload)

    async def list_active(self) -> list[CandidateDocument]:
        cursor = self._collection.find(
            {
                "deprecated_at": None,
                "status": {"$ne": "deprecated"},
            },
            {"_id": 0},
        )
        items = await cursor.to_list(length=None)
        return [CandidateDocument.model_validate(item) for item in items]

    async def list_by_status(self, status: str, *, page: int = 1, page_size: int = 50) -> list[CandidateDocument]:
        offset = max(page - 1, 0) * max(page_size, 1)
        cursor = (
            self._collection.find({"status": status}, {"_id": 0})
            .sort("created_at", -1)
            .skip(offset)
            .limit(max(page_size, 1))
        )
        items = await cursor.to_list(length=max(page_size, 1))
        return [CandidateDocument.model_validate(item) for item in items]

    async def deprecate(self, candidate_id: str, *, status: str = "deprecated", audit_id: str | None = None) -> None:
        update_doc: dict[str, Any] = {
            "$set": {
                "status": status,
                "deprecated_at": datetime.utcnow(),
            }
        }
        if audit_id:
            update_doc["$addToSet"] = {"audit_ids": audit_id}

        await self._collection.update_one(
            {CandidateDocument.primary_key: candidate_id},
            update_doc,
        )


class MongoPositionRepository:
    """持仓集合仓储实现（与策略无关）。"""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._collection = database[PositionDocument.collection_name]

    async def upsert(self, position: PositionDocument) -> PositionDocument:
        payload = position.model_dump()
        created_at = payload.pop("created_at", datetime.utcnow())
        await self._collection.update_one(
            {PositionDocument.primary_key: position.position_id},
            {
                "$set": payload,
                "$setOnInsert": {"created_at": created_at},
            },
            upsert=True,
        )
        return position

    async def upsert_many(self, items: list[PositionDocument]) -> dict[str, int]:
        if not items:
            return {
                "requested": 0,
                "matched": 0,
                "modified": 0,
                "upserted": 0,
            }

        operations: list[UpdateOne] = []
        for item in items:
            payload = item.model_dump()
            created_at = payload.pop("created_at", datetime.utcnow())
            operations.append(
                UpdateOne(
                    {PositionDocument.primary_key: item.position_id},
                    {
                        "$set": payload,
                        "$setOnInsert": {"created_at": created_at},
                    },
                    upsert=True,
                )
            )

        result = await self._collection.bulk_write(operations, ordered=False)
        return {
            "requested": len(items),
            "matched": result.matched_count,
            "modified": result.modified_count,
            "upserted": result.upserted_count,
        }

    async def get_by_id(self, position_id: str) -> PositionDocument | None:
        payload = await self._collection.find_one({PositionDocument.primary_key: position_id}, {"_id": 0})
        return None if payload is None else PositionDocument.model_validate(payload)

    async def list_active(self) -> list[PositionDocument]:
        cursor = self._collection.find(
            {
                "deprecated_at": None,
                "status": {"$ne": "deprecated"},
            },
            {"_id": 0},
        )
        items = await cursor.to_list(length=None)
        return [PositionDocument.model_validate(item) for item in items]

    async def list_by_status(self, status: str, *, page: int = 1, page_size: int = 50) -> list[PositionDocument]:
        offset = max(page - 1, 0) * max(page_size, 1)
        cursor = (
            self._collection.find({"status": status}, {"_id": 0})
            .sort("created_at", -1)
            .skip(offset)
            .limit(max(page_size, 1))
        )
        items = await cursor.to_list(length=max(page_size, 1))
        return [PositionDocument.model_validate(item) for item in items]

    async def deprecate(self, position_id: str, *, status: str = "deprecated", audit_id: str | None = None) -> None:
        update_doc: dict[str, Any] = {
            "$set": {
                "status": status,
                "deprecated_at": datetime.utcnow(),
            }
        }
        if audit_id:
            update_doc["$addToSet"] = {"audit_ids": audit_id}

        await self._collection.update_one(
            {PositionDocument.primary_key: position_id},
            update_doc,
        )


class MongoKlineSyncStateRepository:
    """K 线同步状态仓储实现。"""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._collection = database[KlineSyncStateDocument.collection_name]

    async def get_or_create(self, symbol: str, market: str, interval: str) -> KlineSyncStateDocument:
        """按 (symbol, market, interval) 获取状态文档，不存在时新建。"""
        payload = await self._collection.find_one(
            {"symbol": symbol, "market": market, "interval": interval},
            {"_id": 0},
        )
        if payload is not None:
            return KlineSyncStateDocument.model_validate(payload)
        doc = KlineSyncStateDocument(symbol=symbol, market=market, interval=interval)
        await self._collection.insert_one(doc.model_dump())
        return doc

    async def update(self, state: KlineSyncStateDocument) -> None:
        """更新同步状态（以 state_id 为主键，自动刷新 updated_at）。"""
        payload = state.model_dump()
        payload["updated_at"] = datetime.utcnow()
        await self._collection.update_one(
            {"state_id": state.state_id},
            {"$set": payload},
            upsert=True,
        )


class MongoBackfillProgressRepository:
    """历史回补进度仓储实现。"""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._collection = database[BackfillProgressDocument.collection_name]

    async def get(self, market: str, interval: str, tier: str) -> BackfillProgressDocument | None:
        """按 (market, interval, tier) 获取回补进度文档。"""
        payload = await self._collection.find_one(
            {"market": market, "interval": interval, "tier": tier},
            {"_id": 0},
        )
        return None if payload is None else BackfillProgressDocument.model_validate(payload)

    async def upsert(self, progress: BackfillProgressDocument) -> None:
        """创建或更新回补进度文档（以 progress_id 为主键）。"""
        payload = progress.model_dump()
        payload["updated_at"] = datetime.utcnow()
        await self._collection.update_one(
            {"progress_id": progress.progress_id},
            {"$set": payload},
            upsert=True,
        )

    async def update_cursor(
        self,
        progress_id: str,
        cursor: datetime,
        completion_ratio: float,
    ) -> None:
        """轻量更新：只修改 cursor 和 completion_ratio。"""
        await self._collection.update_one(
            {"progress_id": progress_id},
            {
                "$set": {
                    "cursor": cursor,
                    "completion_ratio": completion_ratio,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
