# Test Framework Layout

This project uses a three-layer test layout:

- `tests/unit/`: pure function/module tests with no external side effects.
- `tests/integration/agent_nodes/`: Agent graph and service integration tests.
- `tests/system/flows/`: end-to-end system flow tests from API request to orchestration.

## Event/Trigger Anti-Pollution Strategy

Event and trigger flow tests must not write to real databases.

- Shared in-memory transaction boundary: `tests/support/in_memory_uow.py`
- FastAPI dependency override fixture: `override_trigger_uow` in `tests/conftest.py`

When writing new trigger flow tests:

1. Add the `override_trigger_uow` fixture to the test signature.
2. Use `TestClient(app)` to call API endpoints.
3. Assert persisted objects via `override_trigger_uow.store`.

## Marker Policy

Markers are auto-assigned by path in `tests/conftest.py`:

- `unit`
- `agent_integration`
- `system_flow`
- `live` (for live external calls)
