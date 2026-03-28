from __future__ import annotations

from agent_trader.agents.state import GraphState


class BacktestRepairGraph:
    async def invoke(self, state: GraphState) -> GraphState:
        next_state = dict(state)
        next_state["report"] = {
            **next_state.get("report", {}),
            "repair": {"status": "pending", "reason": "not implemented"},
        }
        return next_state
