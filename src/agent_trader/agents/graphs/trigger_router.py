from __future__ import annotations

from agent_trader.agents.graphs.research_graph import ResearchGraph
from agent_trader.agents.state import GraphState
from agent_trader.domain.models import TriggerKind


class TriggerRouterGraph:
    """根据触发类型把统一入口路由到后续研究图。"""

    def __init__(self, research_graph: ResearchGraph | None = None) -> None:
        self._research_graph = research_graph or ResearchGraph()

    async def invoke(self, state: GraphState) -> GraphState:
        # 在真正进入子图前先把 trigger kind 规范化，避免后续节点出现分支口径不一致。
        trigger = state.get("trigger", {})
        trigger_kind = TriggerKind(trigger["kind"])
        next_state = dict(state)
        next_state["trigger"] = {**trigger, "kind": trigger_kind.value}
        return await self._research_graph.invoke(next_state)
