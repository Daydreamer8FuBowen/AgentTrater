from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from agent_trader.domain.models import Opportunity, ResearchTask, TriggerKind


def _serialize_datetime(value: datetime) -> datetime:
    """统一保留 domain 层时间对象，交给驱动负责 MySQL DATETIME 编码。"""

    return value


def _serialize_uuid(value: UUID) -> str:
    """MySQL 表结构使用 CHAR(36) 保存 UUID，这里统一转成字符串。"""

    return str(value)


def _opportunity_from_row(row: RowMapping) -> Opportunity:
    """把数据库行映射回 domain dataclass，保证仓储对上层暴露稳定领域对象。"""

    return Opportunity(
        id=UUID(str(row["id"])),
        symbol=str(row["symbol"]),
        trigger_kind=TriggerKind(str(row["trigger_kind"])),
        summary=str(row["summary"]),
        confidence=float(row["confidence"]),
        source_ref=str(row["source_ref"]),
        created_at=row["created_at"],
    )


def _research_task_from_row(row: RowMapping) -> ResearchTask:
    """把 research_tasks 表记录恢复为领域对象。"""

    payload = row["payload"]
    if not isinstance(payload, dict):
        payload = {} if payload is None else dict(payload)

    return ResearchTask(
        id=UUID(str(row["id"])),
        opportunity_id=UUID(str(row["opportunity_id"])),
        trigger_kind=TriggerKind(str(row["trigger_kind"])),
        payload=payload,
        created_at=row["created_at"],
    )


class MySQLOpportunityRepository:
    """`OpportunityRepository` 的 MySQL 实现。

    当前项目还没有建立 SQLAlchemy ORM 映射层，因此这里采用 SQL 文本 + dataclass
    映射的方式实现最小正确版本，后续可平滑迁移到 declarative models。
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, opportunity: Opportunity) -> Opportunity:
        await self._session.execute(
            text(
                """
                INSERT INTO opportunities (
                    id, symbol, trigger_kind, summary, confidence, source_ref, created_at
                ) VALUES (
                    :id, :symbol, :trigger_kind, :summary, :confidence, :source_ref, :created_at
                )
                """
            ),
            {
                "id": _serialize_uuid(opportunity.id),
                "symbol": opportunity.symbol,
                "trigger_kind": opportunity.trigger_kind.value,
                "summary": opportunity.summary,
                "confidence": opportunity.confidence,
                "source_ref": opportunity.source_ref,
                "created_at": _serialize_datetime(opportunity.created_at),
            },
        )
        return opportunity

    async def get(self, opportunity_id: UUID | str) -> Opportunity | None:
        result = await self._session.execute(
            text(
                """
                SELECT id, symbol, trigger_kind, summary, confidence, source_ref, created_at
                FROM opportunities
                WHERE id = :id
                """
            ),
            {"id": str(opportunity_id)},
        )
        row = result.mappings().one_or_none()
        return None if row is None else _opportunity_from_row(row)

    async def list_by_symbol(self, symbol: str) -> Sequence[Opportunity]:
        result = await self._session.execute(
            text(
                """
                SELECT id, symbol, trigger_kind, summary, confidence, source_ref, created_at
                FROM opportunities
                WHERE symbol = :symbol
                ORDER BY created_at DESC
                """
            ),
            {"symbol": symbol},
        )
        return [_opportunity_from_row(row) for row in result.mappings().all()]


class MySQLResearchTaskRepository:
    """`ResearchTaskRepository` 的 MySQL 实现。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, task: ResearchTask) -> ResearchTask:
        await self._session.execute(
            text(
                """
                INSERT INTO research_tasks (
                    id, opportunity_id, trigger_kind, payload, created_at
                ) VALUES (
                    :id, :opportunity_id, :trigger_kind, :payload, :created_at
                )
                """
            ),
            {
                "id": _serialize_uuid(task.id),
                "opportunity_id": _serialize_uuid(task.opportunity_id),
                "trigger_kind": task.trigger_kind.value,
                "payload": task.payload,
                "created_at": _serialize_datetime(task.created_at),
            },
        )
        return task

    async def get(self, task_id: UUID | str) -> ResearchTask | None:
        result = await self._session.execute(
            text(
                """
                SELECT id, opportunity_id, trigger_kind, payload, created_at
                FROM research_tasks
                WHERE id = :id
                """
            ),
            {"id": str(task_id)},
        )
        row = result.mappings().one_or_none()
        return None if row is None else _research_task_from_row(row)

    async def list_by_opportunity(self, opportunity_id: UUID | str) -> Sequence[ResearchTask]:
        result = await self._session.execute(
            text(
                """
                SELECT id, opportunity_id, trigger_kind, payload, created_at
                FROM research_tasks
                WHERE opportunity_id = :opportunity_id
                ORDER BY created_at DESC
                """
            ),
            {"opportunity_id": str(opportunity_id)},
        )
        return [_research_task_from_row(row) for row in result.mappings().all()]


def coerce_json_object(value: Any) -> dict[str, Any]:
    """帮助调用方在读取 JSON 字段时拿到稳定的 dict。"""

    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    return dict(value)
