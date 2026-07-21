"""Unit tests for scenarios and exceptions route endpoints."""

import json
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.app.db import database
from backend.app.main import app


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Set up a temporary test database with schema and seed data."""
    import aiosqlite
    from pathlib import Path

    db_path = tmp_path / "test.db"
    schema_path = Path(__file__).resolve().parent.parent / "app" / "db" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with patch.object(database, "DB_PATH", db_path), \
         patch.object(database, "DB_DIR", tmp_path):
        async with aiosqlite.connect(str(db_path)) as db_conn:
            await db_conn.execute("PRAGMA foreign_keys=ON")
            await db_conn.executescript(schema_sql)
            await db_conn.commit()

        # Seed minimal test data
        async with database.get_db() as db_conn:
            # Insert a scenario
            await db_conn.execute(
                """INSERT INTO scenarios
                   (name, total_travel_hours, total_mileage, total_overtime_hours,
                    continuity_score, objective_score, assignments, routes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("Baseline", 12.5, 45.0, 2.0, 78.5, 92.1,
                 json.dumps([{"carer_id": 1, "visit_id": 1}]),
                 json.dumps([])),
            )
            await db_conn.execute(
                """INSERT INTO scenarios
                   (name, total_travel_hours, total_mileage, total_overtime_hours,
                    continuity_score, objective_score, assignments, routes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("Optimised", 10.0, 38.0, 1.0, 85.0, 96.5,
                 json.dumps([{"carer_id": 1, "visit_id": 2}]),
                 json.dumps([])),
            )
            # Insert an exception (unresolved)
            await db_conn.execute(
                """INSERT INTO exceptions (description, constraint_names, affected_entity_type, affected_entity_id)
                   VALUES (?, ?, ?, ?)""",
                ("Skill mismatch for visit 1", json.dumps(["skill_match"]), "visit", 1),
            )
            # Insert a resolved exception
            await db_conn.execute(
                """INSERT INTO exceptions (description, constraint_names, affected_entity_type, affected_entity_id, is_resolved, resolved_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("Overtime violation", json.dumps(["max_hours"]), "carer", 2, 1, "2025-01-01T10:00:00"),
            )
            await db_conn.commit()
        yield


@pytest_asyncio.fixture
async def client(test_db):
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- Scenario endpoint tests ---


@pytest.mark.asyncio
async def test_list_scenarios(client):
    response = await client.get("/api/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = {d["name"] for d in data}
    assert names == {"Baseline", "Optimised"}


@pytest.mark.asyncio
async def test_get_scenario_by_id(client):
    response = await client.get("/api/scenarios/1")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Baseline"
    assert data["total_travel_hours"] == 12.5
    assert data["objective_score"] == 92.1
    assert data["assignments"] == [{"carer_id": 1, "visit_id": 1}]


@pytest.mark.asyncio
async def test_get_scenario_not_found(client):
    response = await client.get("/api/scenarios/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_scenario(client):
    payload = {
        "name": "New Scenario",
        "total_travel_hours": 8.0,
        "total_mileage": 30.0,
        "total_overtime_hours": 0.5,
        "continuity_score": 90.0,
        "objective_score": 98.0,
        "assignments": [{"carer_id": 2, "visit_id": 3}],
        "routes": [],
    }
    response = await client.post("/api/scenarios", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Scenario"
    assert data["total_travel_hours"] == 8.0
    assert data["id"] == 3


@pytest.mark.asyncio
async def test_create_scenario_duplicate_name(client):
    payload = {
        "name": "Baseline",
        "total_travel_hours": 0,
        "total_mileage": 0,
        "total_overtime_hours": 0,
        "continuity_score": 0,
        "objective_score": 0,
        "assignments": [],
        "routes": [],
    }
    response = await client.post("/api/scenarios", json=payload)
    assert response.status_code == 422
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_compare_scenarios(client):
    response = await client.get("/api/scenarios/compare", params={"ids": "1,2"})
    assert response.status_code == 200
    data = response.json()
    assert "scenario_1" in data
    assert "scenario_2" in data
    assert data["scenario_1"]["name"] == "Baseline"
    assert data["scenario_2"]["name"] == "Optimised"


@pytest.mark.asyncio
async def test_compare_scenarios_fewer_than_two(client):
    response = await client.get("/api/scenarios/compare", params={"ids": "1"})
    assert response.status_code == 400
    assert "At least 2" in response.json()["detail"]


@pytest.mark.asyncio
async def test_compare_scenarios_not_found(client):
    response = await client.get("/api/scenarios/compare", params={"ids": "1,999"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_compare_scenarios_invalid_ids(client):
    response = await client.get("/api/scenarios/compare", params={"ids": "abc,def"})
    assert response.status_code == 400
    assert "integers" in response.json()["detail"]


# --- Exception endpoint tests ---


@pytest.mark.asyncio
async def test_list_exceptions(client):
    response = await client.get("/api/exceptions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_resolve_exception(client):
    response = await client.put("/api/exceptions/1/resolve")
    assert response.status_code == 200
    data = response.json()
    assert data["is_resolved"] is True
    assert data["resolved_at"] is not None


@pytest.mark.asyncio
async def test_resolve_exception_already_resolved_idempotent(client):
    # Exception 2 is already resolved in seed data
    response = await client.put("/api/exceptions/2/resolve")
    assert response.status_code == 200
    data = response.json()
    assert data["already_resolved"] is True
    assert "already resolved" in data["message"]


@pytest.mark.asyncio
async def test_resolve_exception_not_found(client):
    response = await client.put("/api/exceptions/999/resolve")
    assert response.status_code == 404
