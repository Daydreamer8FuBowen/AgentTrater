from fastapi.testclient import TestClient

from agent_trader.api.main import app
from agent_trader.application.services.data_source_gateway import DataSourceRegistry
from agent_trader.ingestion.models import DataRouteKey


def test_source_registry_is_initialized_on_startup() -> None:
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
        assert all(route["enabled"] is True for route in routes)
        assert all(route["priorities"] for route in routes)
        assert all(
            route["priorities"][0] == "baostock"
            for route in routes
            if "baostock" in route["priorities"]
        )


def test_bootstrap_only_inserts_missing_routes() -> None:
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
