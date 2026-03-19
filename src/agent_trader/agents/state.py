from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypedDict
from uuid import UUID, uuid4

from agent_trader.domain.models import Candidate, Opportunity, ResearchTask, StrategyConstraint


class GraphState(TypedDict, total=False):
    """LangGraph 在节点间传递的最小共享状态。"""

    run_id: str
    trigger: dict[str, Any]
    opportunity: Opportunity
    research_task: ResearchTask
    report: dict[str, Any]
    candidate: Candidate
    constraints: list[StrategyConstraint]
    memory_ids: list[str]


@dataclass(slots=True)
class RunMetadata:
    """单次 graph 运行的元信息，后续可扩展 trace_id、重试次数等字段。"""

    trigger_id: UUID
    run_id: UUID = field(default_factory=uuid4)
    started_at: datetime = field(default_factory=datetime.utcnow)
    tags: dict[str, str] = field(default_factory=dict)