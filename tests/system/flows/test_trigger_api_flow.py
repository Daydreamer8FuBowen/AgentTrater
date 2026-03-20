from fastapi.testclient import TestClient

from agent_trader.api.main import app
from support.in_memory_uow import InMemoryUnitOfWork


def test_trigger_submission_returns_job_id(override_trigger_uow: InMemoryUnitOfWork) -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/triggers",
        json={
            "kind": "news",
            "symbol": "AAPL",
            "summary": "Apple receives a strong product demand signal.",
            "metadata": {"source": "unit-test"},
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["job_id"]
    assert len(override_trigger_uow.store.task_runs) == 1
    assert len(override_trigger_uow.store.task_events) == 4
    assert len(override_trigger_uow.store.task_artifacts) == 1
    assert override_trigger_uow.store.commit_count == 2