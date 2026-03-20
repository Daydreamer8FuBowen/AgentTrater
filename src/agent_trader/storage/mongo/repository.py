from __future__ import annotations

from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from agent_trader.storage.mongo.documents import TaskArtifactDocument, TaskEventDocument, TaskRunDocument


def _task_run_update_timestamp() -> dict[str, datetime]:
    return {"updated_at": datetime.utcnow()}


class MongoTaskRunRepository:
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._collection = database[TaskRunDocument.collection_name]

    async def add(self, task_run: TaskRunDocument) -> TaskRunDocument:
        await self._collection.insert_one(task_run.model_dump())
        return task_run

    async def get(self, run_id: str) -> TaskRunDocument | None:
        payload = await self._collection.find_one({TaskRunDocument.primary_key: run_id}, {"_id": 0})
        return None if payload is None else TaskRunDocument.model_validate(payload)

    async def mark_running(self, run_id: str) -> None:
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
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._collection = database[TaskEventDocument.collection_name]

    async def add(self, event: TaskEventDocument) -> TaskEventDocument:
        await self._collection.insert_one(event.model_dump())
        return event


class MongoTaskArtifactRepository:
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._collection = database[TaskArtifactDocument.collection_name]

    async def add(self, artifact: TaskArtifactDocument) -> TaskArtifactDocument:
        payload: dict[str, Any] = artifact.model_dump()
        await self._collection.insert_one(payload)
        return artifact