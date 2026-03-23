"""Mongo 仓库实现（任务相关的增删改查示例）。

本模块包含对 `task_runs`, `task_events`, `task_artifacts` 三个集合的简单仓库实现，
用于演示如何在应用中封装数据库操作。生产环境中可按需扩展更多查询/分页/过滤方法。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from agent_trader.ingestion.models import DataRouteKey
from agent_trader.storage.mongo.documents import (
    NewsDocument,
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
