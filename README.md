# AgentTrader

Agent-centric quantitative research backend built with FastAPI, LangGraph, and a three-store persistence model.

## Development

```bash
uv sync
uv run uvicorn agent_trader.api.main:app --reload --factory
```