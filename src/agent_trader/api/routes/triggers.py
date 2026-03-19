from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from agent_trader.api.dependencies import get_trigger_service
from agent_trader.application.services.trigger_service import TriggerService
from agent_trader.domain.models import TriggerKind
from agent_trader.ingestion.models import ResearchTrigger

router = APIRouter(prefix="/triggers", tags=["triggers"])


class TriggerRequest(BaseModel):
    """外部系统提交研究触发任务的请求体。"""

    kind: TriggerKind
    symbol: str = Field(min_length=1, max_length=32)
    summary: str = Field(min_length=1, max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TriggerResponse(BaseModel):
    """长任务风格的统一响应，当前只返回 job_id 和排队状态。"""

    job_id: str
    status: str


@router.post("", response_model=TriggerResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_trigger(
    payload: TriggerRequest,
    trigger_service: TriggerService = Depends(get_trigger_service),
) -> TriggerResponse:
    # API 层只负责请求校验和协议转换，实际业务编排下沉到应用服务层。
    result = await trigger_service.submit_trigger(
        ResearchTrigger(
            trigger_kind=payload.kind,
            symbol=payload.symbol,
            summary=payload.summary,
            metadata=payload.metadata,
        )
    )
    return TriggerResponse(**result)