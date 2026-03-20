from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agent_trader.agents.state import GraphState


class ResearchGraph:
    """多 Agent 研究主图 demo：分析 -> 复核 -> 汇总。"""

    def __init__(self) -> None:
        workflow = StateGraph(GraphState)
        workflow.add_node("analyst", self._analyst_node)
        workflow.add_node("reviewer", self._reviewer_node)
        workflow.add_node("synthesizer", self._synthesizer_node)
        workflow.add_edge(START, "analyst")
        workflow.add_edge("analyst", "reviewer")
        workflow.add_edge("reviewer", "synthesizer")
        workflow.add_edge("synthesizer", END)
        self._app = workflow.compile()

    async def _analyst_node(self, state: GraphState) -> GraphState:
        trigger = state.get("trigger", {})
        opportunity = state.get("opportunity")
        symbol = trigger.get("symbol") or (opportunity.symbol if opportunity else "UNKNOWN")
        reason = f"trigger={trigger.get('kind', 'unknown')} symbol={symbol}"

        next_state = dict(state)
        next_state["report"] = {
            **next_state.get("report", {}),
            "analysis": {
                "status": "done",
                "summary": "Demo analyst produced an initial thesis.",
                "reasoning": [reason],
            },
            "pipeline": ["analyst"],
        }
        return next_state

    async def _reviewer_node(self, state: GraphState) -> GraphState:
        report = dict(state.get("report", {}))
        pipeline = list(report.get("pipeline", []))
        pipeline.append("reviewer")

        checks = [
            "basic trigger fields present",
            "opportunity context available",
        ]

        next_state = dict(state)
        next_state["report"] = {
            **report,
            "review": {
                "status": "done",
                "checks": checks,
                "decision": "pass",
            },
            "pipeline": pipeline,
        }
        return next_state

    async def _synthesizer_node(self, state: GraphState) -> GraphState:
        report = dict(state.get("report", {}))
        pipeline = list(report.get("pipeline", []))
        pipeline.append("synthesizer")

        summary = "Demo research finished: analyst and reviewer completed with pass decision."
        reasoning = [
            "This is a deterministic demo graph without LLM/tool calls.",
            "Replace node internals to connect real data tools and model inference.",
        ]

        next_state = dict(state)
        next_state["report"] = {
            **report,
            "summary": summary,
            "reasoning": reasoning,
            "pipeline": pipeline,
        }
        return next_state

    async def invoke(self, state: GraphState) -> GraphState:
        result = await self._app.ainvoke(state)
        return result