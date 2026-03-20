from __future__ import annotations

import pytest

from agent_trader.agents.graphs.research_graph import ResearchGraph
from agent_trader.domain.models import TriggerKind


@pytest.mark.asyncio
async def test_research_graph_runs_demo_pipeline_in_order() -> None:
    graph = ResearchGraph()

    state = {
        "run_id": "demo-run",
        "trigger": {"kind": TriggerKind.NEWS.value, "symbol": "AAPL"},
    }

    result = await graph.invoke(state)

    assert "report" in result
    report = result["report"]
    assert report["pipeline"] == ["analyst", "reviewer", "synthesizer"]
    assert report["review"]["decision"] == "pass"
    assert "Demo research finished" in report["summary"]
