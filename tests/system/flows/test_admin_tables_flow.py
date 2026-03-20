from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient

from agent_trader.api.dependencies import get_table_admin_service
from agent_trader.api.main import app


class _FakeTableAdminService:
    def list_tables(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "agent_definitions",
                "primary_key": "id",
                "columns": ["id", "agent_code", "agent_name"],
                "searchable_columns": ["agent_code", "agent_name"],
                "json_columns": [],
            }
        ]

    async def query_rows(
        self,
        table_name: str,
        *,
        page: int,
        page_size: int,
        keyword: str | None = None,
        filters: dict[str, Any] | None = None,
        sort_by: str | None = None,
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        del keyword, filters, sort_by, sort_order
        if table_name != "agent_definitions":
            raise ValueError("Unsupported table")
        return {
            "table": table_name,
            "page": page,
            "page_size": page_size,
            "total": 1,
            "items": [{"id": 1, "agent_code": "research", "agent_name": "Research Agent"}],
        }

    async def get_row(self, table_name: str, row_id: str) -> dict[str, Any] | None:
        if table_name != "agent_definitions":
            raise ValueError("Unsupported table")
        if row_id != "1":
            return None
        return {"id": 1, "agent_code": "research", "agent_name": "Research Agent"}

    async def update_row(
        self,
        table_name: str,
        row_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        if table_name != "agent_definitions":
            raise ValueError("Unsupported table")
        if row_id != "1":
            return None
        if "id" in updates:
            raise ValueError("No editable columns in update payload")
        return {"id": 1, "agent_code": "research", "agent_name": updates.get("agent_name", "Research Agent")}


async def _override_table_admin_service() -> AsyncIterator[_FakeTableAdminService]:
    yield _FakeTableAdminService()


def test_list_manageable_tables() -> None:
    app.dependency_overrides[get_table_admin_service] = _override_table_admin_service
    try:
        client = TestClient(app)
        response = client.get("/api/v1/admin/tables")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "agent_definitions"
    finally:
        app.dependency_overrides.clear()


def test_query_table_rows() -> None:
    app.dependency_overrides[get_table_admin_service] = _override_table_admin_service
    try:
        client = TestClient(app)
        response = client.get("/api/v1/admin/tables/agent_definitions/rows?page=1&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["table"] == "agent_definitions"
        assert data["total"] == 1
    finally:
        app.dependency_overrides.clear()


def test_get_table_row_not_found() -> None:
    app.dependency_overrides[get_table_admin_service] = _override_table_admin_service
    try:
        client = TestClient(app)
        response = client.get("/api/v1/admin/tables/agent_definitions/rows/2")

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_update_table_row() -> None:
    app.dependency_overrides[get_table_admin_service] = _override_table_admin_service
    try:
        client = TestClient(app)
        response = client.patch(
            "/api/v1/admin/tables/agent_definitions/rows/1",
            json={"updates": {"agent_name": "Risk Agent"}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_name"] == "Risk Agent"
    finally:
        app.dependency_overrides.clear()


def test_update_table_row_requires_payload() -> None:
    app.dependency_overrides[get_table_admin_service] = _override_table_admin_service
    try:
        client = TestClient(app)
        response = client.patch(
            "/api/v1/admin/tables/agent_definitions/rows/1",
            json={"updates": {}},
        )

        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()