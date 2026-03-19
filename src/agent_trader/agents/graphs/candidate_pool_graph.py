from __future__ import annotations

from agent_trader.agents.state import GraphState
from agent_trader.domain.models import Candidate, CandidateStatus


class CandidatePoolGraph:
    async def invoke(self, state: GraphState) -> GraphState:
        opportunity = state.get("opportunity")
        if opportunity is None:
            return state

        next_state = dict(state)
        next_state["candidate"] = Candidate(
            symbol=opportunity.symbol,
            thesis=opportunity.summary,
            status=CandidateStatus.RESEARCHING,
            score=opportunity.confidence,
            constraints=[],
        )
        return next_state