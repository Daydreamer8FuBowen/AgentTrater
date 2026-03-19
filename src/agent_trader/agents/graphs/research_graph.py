from __future__ import annotations

from typing import Any

from agent_trader.agents.state import GraphState


class ResearchGraph:
    """多 Agent 研究主图占位实现。"""

    async def invoke(self, state: GraphState) -> GraphState:
        # 当前先返回一个稳定的占位报告，后续会替换为 analyst / reviewer / synthesizer 等节点协作。
        report: dict[str, Any] = {
            "summary": "research placeholder",
            "reasoning": ["graph scaffold initialized"],
        }
        next_state = dict(state)
        next_state["report"] = report
        return next_state