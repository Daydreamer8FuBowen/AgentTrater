from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest

from agent_trader.api.dependencies import get_uow
from agent_trader.api.main import app
from support.in_memory_uow import InMemoryEventStore, InMemoryUnitOfWork


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Iterator[None]:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def in_memory_event_store() -> InMemoryEventStore:
    return InMemoryEventStore()


@pytest.fixture
def in_memory_uow(in_memory_event_store: InMemoryEventStore) -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork(store=in_memory_event_store)


@pytest.fixture
def override_trigger_uow(in_memory_uow: InMemoryUnitOfWork) -> InMemoryUnitOfWork:
    async def _override_uow() -> AsyncIterator[InMemoryUnitOfWork]:
        yield in_memory_uow

    app.dependency_overrides[get_uow] = _override_uow
    return in_memory_uow


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = Path(str(item.fspath)).as_posix()
        if "/tests/unit/" in path:
            item.add_marker(pytest.mark.unit)
        elif "/tests/integration/agent_nodes/" in path:
            item.add_marker(pytest.mark.agent_integration)
        elif "/tests/system/flows/" in path:
            item.add_marker(pytest.mark.system_flow)
            if "live" in Path(path).name:
                item.add_marker(pytest.mark.live)
