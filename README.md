# AgentTrader

Agent-centric quantitative research backend built with FastAPI, LangGraph, MongoDB, and InfluxDB.

## Development

```bash
uv sync
uv run uvicorn agent_trader.api.main:app --reload
```

Local infrastructure:

```bash
docker compose up -d mongo influxdb
```

Frontend admin console:

```bash
cd frontend/admin-console
npm install
npm run dev
```