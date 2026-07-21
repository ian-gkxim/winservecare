"""Integration tests for carer and patient API endpoints."""

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
            await db_conn.execute(
                """INSERT INTO carers (name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("Alice", 51.5, -0.1, json.dumps(["personal_care", "medication"]), 8.0, 6.0, 30),
            )
            await db_conn.execute(
                """INSERT INTO carers (name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("Bob", 51.6, -0.2, json.dumps(["personal_care"]), 10.0, 6.0, 30),
            )
            await db_conn.execute(
                """INSERT INTO patients (name, address, lat, lng, preferences, priority, continuity_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("Patient A", "1 High St", 51.51, -0.11, json.dumps(["morning"]), "high", 85.0),
            )
            await db_conn.execute(
                """INSERT INTO patients (name, address, lat, lng, preferences, priority, continuity_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("Patient B", "2 Low St", 51.52, -0.12, json.dumps(["evening"]), "low", 60.0),
            )
            await db_conn.commit()
        yield


@pytest_asyncio.fixture
async def client(test_db):
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- Carers GET tests ---


@pytest.mark.asyncio
async def test_get_carers_returns_all(client):
    response = await client.get("/api/carers")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Alice"
    assert data[0]["skills"] == ["personal_care", "medication"]
    assert data[1]["name"] == "Bob"


@pytest.mark.asyncio
async def test_get_carers_response_shape(client):
    response = await client.get("/api/carers")
    assert response.status_code == 200
    carer = response.json()[0]
    assert "id" in carer
    assert "name" in carer
    assert "home_lat" in carer
    assert "home_lng" in carer
    assert "skills" in carer
    assert "max_working_hours" in carer
    assert "max_continuous_hours" in carer
    assert "min_break_minutes" in carer


# --- Carers PUT tests ---


@pytest.mark.asyncio
async def test_put_carer_success(client):
    response = await client.put("/api/carers/1", json={"name": "Alice Smith"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Alice Smith"
    # Unchanged fields preserved
    assert data["skills"] == ["personal_care", "medication"]
    assert data["max_working_hours"] == 8.0


@pytest.mark.asyncio
async def test_put_carer_update_multiple_fields(client):
    response = await client.put(
        "/api/carers/1",
        json={"name": "Alice Updated", "max_working_hours": 9.0, "skills": ["personal_care"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Alice Updated"
    assert data["max_working_hours"] == 9.0
    assert data["skills"] == ["personal_care"]


@pytest.mark.asyncio
async def test_put_carer_not_found(client):
    response = await client.put("/api/carers/999", json={"name": "Ghost"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_put_carer_empty_name_returns_422(client):
    response = await client.put("/api/carers/1", json={"name": "   "})
    assert response.status_code == 422
    data = response.json()
    assert "errors" in data["detail"]


@pytest.mark.asyncio
async def test_put_carer_invalid_max_working_hours(client):
    response = await client.put("/api/carers/1", json={"max_working_hours": 25.0})
    assert response.status_code == 422


# --- Patients GET tests ---


@pytest.mark.asyncio
async def test_get_patients_returns_all(client):
    response = await client.get("/api/patients")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Patient A"
    assert data[0]["priority"] == "high"
    assert data[1]["name"] == "Patient B"


@pytest.mark.asyncio
async def test_get_patients_response_shape(client):
    response = await client.get("/api/patients")
    assert response.status_code == 200
    patient = response.json()[0]
    assert "id" in patient
    assert "name" in patient
    assert "address" in patient
    assert "lat" in patient
    assert "lng" in patient
    assert "preferences" in patient
    assert "priority" in patient
    assert "continuity_score" in patient


# --- Patients PUT tests ---


@pytest.mark.asyncio
async def test_put_patient_success(client):
    response = await client.put("/api/patients/1", json={"name": "Patient A Updated"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Patient A Updated"
    # Unchanged fields preserved
    assert data["priority"] == "high"
    assert data["continuity_score"] == 85.0


@pytest.mark.asyncio
async def test_put_patient_update_priority(client):
    response = await client.put("/api/patients/1", json={"priority": "low"})
    assert response.status_code == 200
    data = response.json()
    assert data["priority"] == "low"


@pytest.mark.asyncio
async def test_put_patient_not_found(client):
    response = await client.put("/api/patients/999", json={"name": "Ghost"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_put_patient_empty_name_returns_422(client):
    response = await client.put("/api/patients/1", json={"name": "   "})
    assert response.status_code == 422
    data = response.json()
    assert "errors" in data["detail"]


@pytest.mark.asyncio
async def test_put_patient_invalid_priority(client):
    response = await client.put("/api/patients/1", json={"priority": "critical"})
    assert response.status_code == 422
