from fastapi.testclient import TestClient

from agent_trader.api.main import app


async def _noop_symbol_bootstrap(*args, **kwargs) -> None:  # noqa: ARG001
    return None


def test_healthcheck(monkeypatch) -> None:
    monkeypatch.setattr("agent_trader.api.main._bootstrap_basic_info_symbols_if_empty", _noop_symbol_bootstrap)
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}