from __future__ import annotations

from agent_trader.agents.graphs.trigger_router import TriggerRouterGraph
from agent_trader.domain.models import TriggerKind
from agent_trader.ingestion.models import ResearchTrigger
from agent_trader.storage.base import UnitOfWork
from agent_trader.storage.mongo.documents import TaskArtifactDocument, TaskEventDocument, TaskRunDocument


class TriggerService:
    """承接外部 trigger，并把它推进到机会、任务和 graph 编排层。"""

    def __init__(self, unit_of_work: UnitOfWork, router_graph: TriggerRouterGraph | None = None) -> None:
        self._unit_of_work = unit_of_work
        self._router_graph = router_graph or TriggerRouterGraph()

    async def submit_trigger(self, trigger: ResearchTrigger) -> dict[str, str]:
        task_run = TaskRunDocument(
            trigger={
                "trigger_id": str(trigger.id),
                "kind": TriggerKind(trigger.trigger_kind).value,
                "source": str(trigger.metadata.get("source", "unknown")),
                "summary": trigger.summary,
            },
            context={
                "symbol": trigger.symbol,
                "metadata": trigger.metadata,
            },
            agent={
                "agent_id": "agent_research_main",
                "agent_release_id": "unassigned",
            },
            graph={
                "graph_name": "research_graph",
                "graph_version": "v1",
            },
            execution={
                "retry_count": 0,
            },
            metrics={
                "event_count": 0,
                "artifact_count": 0,
            },
            search_tags=[trigger.symbol, TriggerKind(trigger.trigger_kind).value, "research"],
        )

        async with self._unit_of_work as uow:
            await uow.task_runs.add(task_run)
            await uow.task_events.add(
                TaskEventDocument(
                    run_id=task_run.run_id,
                    seq=1,
                    event_type="run.created",
                    payload={
                        "status": task_run.status,
                        "trigger": task_run.trigger,
                    },
                )
            )
            await uow.task_runs.mark_running(task_run.run_id)
            await uow.task_events.add(
                TaskEventDocument(
                    run_id=task_run.run_id,
                    seq=2,
                    event_type="run.started",
                    payload={"status": "running"},
                )
            )

        state = {
            "run_id": task_run.run_id,
            "trigger": {"kind": trigger.trigger_kind.value, "symbol": trigger.symbol},
        }
        try:
            report = await self._router_graph.invoke(state)
        except Exception as exc:
            async with self._unit_of_work as uow:
                await uow.task_runs.mark_failed(task_run.run_id, error_message=str(exc))
                await uow.task_events.add(
                    TaskEventDocument(
                        run_id=task_run.run_id,
                        seq=3,
                        event_type="run.failed",
                        payload={"message": str(exc)},
                    )
                )
            raise

        summary = None
        report_payload = report.get("report") if isinstance(report, dict) else None
        if isinstance(report_payload, dict):
            candidate_summary = report_payload.get("summary")
            summary = str(candidate_summary) if candidate_summary is not None else None

        final_artifact = TaskArtifactDocument(
            run_id=task_run.run_id,
            node_id="synthesizer",
            artifact_type="final_report",
            content=report_payload or {},
            size_bytes=len(str(report_payload or {})),
        )

        async with self._unit_of_work as uow:
            await uow.task_artifacts.add(final_artifact)
            await uow.task_events.add(
                TaskEventDocument(
                    run_id=task_run.run_id,
                    seq=3,
                    event_type="artifact.created",
                    payload={
                        "artifact_id": final_artifact.artifact_id,
                        "artifact_type": final_artifact.artifact_type,
                    },
                )
            )
            await uow.task_runs.mark_completed(task_run.run_id, result_summary=summary)
            await uow.task_events.add(
                TaskEventDocument(
                    run_id=task_run.run_id,
                    seq=4,
                    event_type="run.completed",
                    payload={"summary": summary},
                )
            )
        return {"job_id": task_run.run_id, "status": "queued"}