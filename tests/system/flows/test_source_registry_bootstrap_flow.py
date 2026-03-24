from fastapi.testclient import TestClient

from agent_trader.api.main import app
from agent_trader.application.data_access.gateway import DataSourceRegistry
from agent_trader.ingestion.models import DataRouteKey


async def _noop_symbol_bootstrap(*args, **kwargs) -> None:  # noqa: ARG001
    return None


def test_source_registry_is_initialized_on_startup(monkeypatch) -> None:
    monkeypatch.setattr("agent_trader.api.main._bootstrap_basic_info_symbols_if_empty", _noop_symbol_bootstrap)
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200

        registry = getattr(app.state, "source_registry", None)
        assert isinstance(registry, DataSourceRegistry)

        names = registry.names()
        assert "baostock" in names

        database = app.state.mongo_manager.database
        async def _load_routes() -> list[dict]:
            cursor = database["source_priority_routes"].find({}, {"_id": 0})
            return await cursor.to_list(length=1000)

        routes = client.portal.call(_load_routes)
        assert routes
        assert all(route["priorities"] for route in routes)
        bootstrapped_routes = [
            route
            for route in routes
            if route.get("metadata", {}).get("bootstrap") is True
        ]
        assert bootstrapped_routes
        assert all(route["enabled"] is True for route in bootstrapped_routes)
        assert all(
            route["priorities"][0] == "baostock"
            for route in routes
            if "baostock" in route["priorities"]
        )


def test_bootstrap_only_inserts_missing_routes(monkeypatch) -> None:
    monkeypatch.setattr("agent_trader.api.main._bootstrap_basic_info_symbols_if_empty", _noop_symbol_bootstrap)
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200

        database = app.state.mongo_manager.database

        async def _prepare_and_bootstrap() -> tuple[dict | None, dict | None]:
            from agent_trader.api.main import _build_source_registry, _rebuild_default_source_priorities

            collection = database["source_priority_routes"]

            registry = _build_source_registry()
            route_ids: list[str] = []
            for source_name in registry.names():
                provider = registry.get(source_name)
                if provider is None:
                    continue
                capabilities = getattr(provider, "capabilities", None)
                if not callable(capabilities):
                    continue
                for spec in capabilities():
                    markets = spec.markets or (None,)
                    intervals = spec.intervals or (None,)
                    for market in markets:
                        for interval in intervals:
                            route_ids.append(
                                DataRouteKey(
                                    capability=spec.capability,
                                    market=market,
                                    interval=interval,
                                ).as_storage_key()
                            )

            assert len(route_ids) >= 2
            existing_route_id = route_ids[0]
            missing_route_id = route_ids[1]

            await collection.delete_many({"route_id": {"$in": [existing_route_id, missing_route_id]}})
            await collection.insert_one(
                {
                    "route_id": existing_route_id,
                    "capability": existing_route_id.split(":", 1)[0],
                    "market": None,
                    "interval": None,
                    "priorities": ["manual-source"],
                    "enabled": False,
                    "metadata": {"custom": True},
                }
            )

            await _rebuild_default_source_priorities(database, registry)

            existing = await collection.find_one({"route_id": existing_route_id}, {"_id": 0})
            added = await collection.find_one({"route_id": missing_route_id}, {"_id": 0})
            return existing, added

        existing, added = client.portal.call(_prepare_and_bootstrap)

        assert existing is not None
        assert existing["priorities"] == ["manual-source"]
        assert existing["enabled"] is False
        assert existing["metadata"] == {"custom": True}

        assert added is not None
        assert added["enabled"] is True
        assert added["metadata"].get("bootstrap") is True


def test_basic_info_symbol_bootstrap_only_runs_when_collection_empty(monkeypatch) -> None:
    from agent_trader.api import main as main_mod
    from agent_trader.storage.mongo.documents import BasicInfoDocument

    original_bootstrap = main_mod._bootstrap_basic_info_symbols_if_empty
    monkeypatch.setattr(main_mod, "_bootstrap_basic_info_symbols_if_empty", _noop_symbol_bootstrap)

    temp_collection = "basic_infos_test_bootstrap"
    monkeypatch.setattr(BasicInfoDocument, "collection_name", temp_collection)

    class _FakeService:
        def __init__(self, database):
            self._database = database
            self.calls = 0

        async def sync_basic_info_snapshot(self, market=None):  # noqa: ARG002
            self.calls += 1
            await self._database[temp_collection].insert_one(
                {
                    "symbol": "600000.SH",
                    "name": "Bootstrap Co",
                    "market": "sh",
                    "source_trace": ["bootstrap"],
                    "conflict_fields": [],
                    "metadata": {"bootstrap": True},
                }
            )
            return {
                "requested_sources": 1,
                "input_count": 1,
                "dedup_count": 1,
                "persisted": {"requested": 1, "matched": 0, "modified": 0, "upserted": 1},
                "failed_sources": [],
            }

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200

        database = app.state.mongo_manager.database
        service = _FakeService(database)

        monkeypatch.setattr(main_mod, "_bootstrap_basic_info_symbols_if_empty", original_bootstrap)

        monkeypatch.setattr(
            main_mod,
            "_build_basic_info_aggregation_service",
            lambda database, registry: service,  # noqa: ARG005
        )

        async def _exercise() -> tuple[int, int]:
            from agent_trader.api.main import _build_source_registry, _bootstrap_basic_info_symbols_if_empty

            await database[temp_collection].delete_many({})
            try:
                registry = _build_source_registry()
                await _bootstrap_basic_info_symbols_if_empty(database, registry)
                first_count = await database[temp_collection].count_documents({})
                await _bootstrap_basic_info_symbols_if_empty(database, registry)
                second_count = await database[temp_collection].count_documents({})
                return first_count, second_count
            finally:
                await database[temp_collection].delete_many({})

        first_count, second_count = client.portal.call(_exercise)

        assert service.calls == 1
        assert first_count == 1
        assert second_count == 1
