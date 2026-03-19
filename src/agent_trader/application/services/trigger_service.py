from __future__ import annotations

from agent_trader.agents.graphs.trigger_router import TriggerRouterGraph
from agent_trader.domain.models import Opportunity, ResearchTask, TriggerKind
from agent_trader.ingestion.models import ResearchTrigger
from agent_trader.storage.base import UnitOfWork


class TriggerService:
    """承接外部 trigger，并把它推进到机会、任务和 graph 编排层。"""

    def __init__(self, unit_of_work: UnitOfWork, router_graph: TriggerRouterGraph | None = None) -> None:
        self._unit_of_work = unit_of_work
        self._router_graph = router_graph or TriggerRouterGraph()

    async def submit_trigger(self, trigger: ResearchTrigger) -> dict[str, str]:
        # 第一阶段先把 trigger 映射为结构化 Opportunity 和 ResearchTask，确保采集层与研究层解耦。
        opportunity = Opportunity(
            symbol=trigger.symbol,
            trigger_kind=TriggerKind(trigger.trigger_kind),
            summary=trigger.summary,
            confidence=0.5,
            source_ref=str(trigger.id),
        )
        research_task = ResearchTask(
            opportunity_id=opportunity.id,
            trigger_kind=trigger.trigger_kind,
            payload=trigger.metadata,
        )

        async with self._unit_of_work as uow:
            await uow.opportunities.add(opportunity)
            await uow.research_tasks.add(research_task)

        # graph 状态只携带后续推理真正需要的上下文，避免把 API 层对象直接泄漏到 Agent 内部。
        state = {
            "run_id": str(research_task.id),
            "trigger": {"kind": trigger.trigger_kind.value, "symbol": trigger.symbol},
            "opportunity": opportunity,
            "research_task": research_task,
        }
        await self._router_graph.invoke(state)
        return {"job_id": str(research_task.id), "status": "queued"}