from fastapi.testclient import TestClient

from agent_trader.api.main import app


def test_trigger_submission_returns_job_id() -> None:
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