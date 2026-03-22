from fastapi.testclient import TestClient

from agent_trader.api.main import app
from agent_trader.application.services.data_source_gateway import DataSourceRegistry


def test_source_registry_is_initialized_on_startup() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200

        registry = getattr(app.state, "source_registry", None)
        assert isinstance(registry, DataSourceRegistry)

        names = registry.names()
        assert "baostock" in names
