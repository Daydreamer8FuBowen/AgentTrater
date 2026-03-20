from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agent_trader.agents.graphs.trigger_router import TriggerRouterGraph
from agent_trader.domain.models import TriggerKind


@pytest.mark.asyncio
async def test_trigger_router_graph_normalizes_kind_and_forwards_state() -> None:
    research_graph = AsyncMock()
    research_graph.invoke.return_value = {"ok": True}
    router = TriggerRouterGraph(research_graph=research_graph)

    state = {
        "run_id": "test-run",
        "trigger": {"kind": TriggerKind.NEWS, "symbol": "AAPL"},
    }

    result = await router.invoke(state)

    assert result == {"ok": True}
    research_graph.invoke.assert_awaited_once()
    forwarded_state = research_graph.invoke.await_args.args[0]
    assert forwarded_state["trigger"]["kind"] == "news"
    assert forwarded_state["trigger"]["symbol"] == "AAPL"
