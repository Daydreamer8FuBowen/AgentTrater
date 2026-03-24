from __future__ import annotations

from fastapi.testclient import TestClient

from agent_trader.api.dependencies import get_basic_info_aggregation_service
from agent_trader.api.main import app


async def _noop_symbol_bootstrap(*args, **kwargs) -> None:  # noqa: ARG001
    return None


class _FakeBasicInfoAggregationService:
    async def sync_basic_info_snapshot(self, market=None):
        return {
            "requested_sources": 2,
            "input_count": 10,
            "dedup_count": 8,
            "persisted": {
                "requested": 8,
                "matched": 5,
                "modified": 5,
                "upserted": 3,
            },
            "failed_sources": [
                {"source": "broken", "error": "timeout"},
            ],
        }


def test_refresh_basic_info_api_returns_incremental_sync_summary(monkeypatch) -> None:
    monkeypatch.setattr("agent_trader.api.main._bootstrap_basic_info_symbols_if_empty", _noop_symbol_bootstrap)

    async def _override_service() -> _FakeBasicInfoAggregationService:
        return _FakeBasicInfoAggregationService()

    app.dependency_overrides[get_basic_info_aggregation_service] = _override_service
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/data/basic-info/refresh?market=sse")

        assert response.status_code == 200
        body = response.json()
        assert body["requested_sources"] == 2
        assert body["input_count"] == 10
        assert body["dedup_count"] == 8
        assert body["persisted"]["matched"] == 5
        assert body["persisted"]["upserted"] == 3
        assert body["failed_sources"] == [{"source": "broken", "error": "timeout"}]
    finally:
        app.dependency_overrides.clear()
